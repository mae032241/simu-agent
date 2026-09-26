"""Materialize TCAD projects from solver-neutral source declarations.

The control plane validates paths, exact source anchors, plan values, units,
and hashes.  It deliberately does not parse or generate solver-language code.
Physical meaning remains the author/reviewer's responsibility.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Mapping, Sequence

from pydantic import Field, ValidationError, field_validator
from scidiscovery.artifact_agent.schema.experiment import (
    ComparisonVariable,
    ExperimentPortfolio,
)

from .execution_control import SolverCapabilitySnapshot, StrictModel
from .project_packager import (
    CaseParameterBinding,
    DeclaredCaseAnchor,
    DeckFile,
    DeckProjectDraft,
    MaterializationFinding,
    ProjectExpectedOutput,
    ProjectMaterializationReport,
    ProjectPreflightAttestation,
    ProjectResourceLimits,
    deck_scoped_comparison_variable,
)


MATERIALIZER_PROFILE = "tcad.project-materializer.declared-source.v2"
MATERIALIZATION_CONTRACT_PROFILE = "tcad.project-declaration-contract.v2"


def _safe_relative_path(value: str) -> str:
    if value.startswith("/") or "\\" in value or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ValueError("unsafe relative path")
    return value


class DeclaredRawOutput(StrictModel):
    """One author-declared solver-native output path.

    The declaration is intentionally syntax-free.  Independent review, rather
    than the control plane, establishes that the authored deck produces it.
    """

    name: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    relative_path: str = Field(min_length=1, max_length=1024)
    media_type: str = Field(min_length=3, max_length=255)

    _safe_path = field_validator("relative_path")(_safe_relative_path)


class DeckSourceDeclarations(StrictModel):
    schema_version: Annotated[int, Field(ge=2, le=2)] = 2
    profile: str = Field(
        default=MATERIALIZATION_CONTRACT_PROFILE,
        pattern=r"^tcad\.project-declaration-contract\.v2$",
    )
    entrypoint: str = Field(min_length=1, max_length=1024)
    development_initialization_entrypoint: str | None = Field(
        default=None, min_length=1, max_length=1024
    )
    case_anchors: tuple[DeclaredCaseAnchor, ...] = Field(max_length=100000)
    raw_outputs: tuple[DeclaredRawOutput, ...] = Field(default=(), max_length=4096)
    collect_generated_outputs: bool | None = None
    resource_limits: ProjectResourceLimits | None = None

    _safe_entrypoint = field_validator("entrypoint")(_safe_relative_path)

    @field_validator("development_initialization_entrypoint")
    @classmethod
    def _safe_optional_entrypoint(cls, value: str | None) -> str | None:
        return None if value is None else _safe_relative_path(value)


class ProjectMaterializationError(ValueError):
    """A bounded set of deterministic declaration/plan contradictions."""

    def __init__(self, report: ProjectMaterializationReport) -> None:
        self.report = report
        first = report.findings[0] if report.findings else None
        super().__init__(
            "TCAD project materialization failed"
            + (f": {first.reason_code}: {first.message}" if first else "")
        )

    @property
    def details(self) -> tuple[dict[str, str], ...]:
        values: list[dict[str, str]] = []
        for finding in self.report.findings[:64]:
            path = "$.deck.declarations"
            if finding.source_path is not None:
                path += f".files[{finding.source_path}]"
            scope = "/".join(
                item
                for item in (
                    finding.experiment_key,
                    finding.case_key,
                    finding.variable_key,
                )
                if item is not None
            )
            message = finding.message + (f"; scope={scope}" if scope else "")
            if finding.expected is not None:
                message += f"; expected={finding.expected}"
            if finding.observed is not None:
                message += f"; observed={finding.observed}"
            values.append(
                {"path": path, "message": message[:4096], "type": finding.reason_code}
            )
        return tuple(values)


def materialization_contract(experiment_plan: bytes) -> dict[str, object]:
    """Project only solver-neutral cases, values, units, and declaration rules."""

    portfolio = ExperimentPortfolio.model_validate_json(experiment_plan, strict=True)
    proposals: list[dict[str, object]] = []
    for proposal in portfolio.proposals:
        contract = proposal.comparison_contract
        if contract is None:
            variables: tuple[ComparisonVariable, ...] = ()
        else:
            variables = tuple(
                item
                for item in contract.variables
                if deck_scoped_comparison_variable(item.scientific_path)
            )
        values: list[dict[str, object]] = []
        for variable in variables:
            values.extend(
                {
                    "case_key": item.case_key,
                    "variable_key": variable.variable_key,
                    "scientific_path": variable.scientific_path,
                    "value": item.value,
                    "unit": variable.unit,
                }
                for item in variable.expectations
            )
        proposals.append(
            {
                "experiment_key": proposal.experiment_key,
                "case_keys": [item.case_key for item in proposal.cases],
                "controls": values,
            }
        )
    return {
        "schema_version": 2,
        "profile": MATERIALIZATION_CONTRACT_PROFILE,
        "responsibility": (
            "Control validates declarations and provenance only; it does not parse "
            "or generate solver-language code."
        ),
        "declaration_file": "deck/declarations.json",
        "required_fields": ["entrypoint", "case_anchors", "resource_limits"],
        "resource_budget_rule": "Declare wall_time_seconds, cpu_time_seconds, max_memory_bytes, max_output_bytes and max_storage_bytes. These are request bounds; administrator execution policy owns autonomous authority.",
        "case_anchor_fields": [
            "experiment_key",
            "case_key",
            "relative_path",
            "locator",
        ],
        "source_rules": {
            "locator_occurrences": 1,
            "locator_interpretation": "independent_deck_review",
            "solver_syntax_parsing": False,
        },
        "raw_output_fields": [],
        "generated_output_collection": "all changed regular files in the isolated work directory, bounded by job limits",
        "control_generated_output_fields": ["capture", "max_bytes"],
        "output_instruction": (
            "Generated solver files are collected from the isolated work directory. "
            "Do not enumerate adaptive frames in raw_outputs; control builds a hashed file manifest."
        ),
        "proposals": proposals,
    }


def materialization_contract_json(experiment_plan: bytes) -> bytes:
    return _pretty_json(materialization_contract(experiment_plan))


def declarations_template(
    experiment_plan: bytes, *, base_project: DeckProjectDraft | None = None
) -> dict[str, object]:
    """Build a mechanical declaration template without generating deck code."""

    portfolio = ExperimentPortfolio.model_validate_json(experiment_plan, strict=True)
    existing: dict[tuple[str, str], tuple[str, str]] = {}
    if base_project is not None:
        for item in (
            base_project.case_parameter_bindings
            if base_project.case_anchors is None else base_project.case_anchors
        ):
            existing.setdefault(
                (item.experiment_key, item.case_key),
                (item.relative_path, item.locator),
            )
    anchors: list[dict[str, object]] = []
    for proposal in portfolio.proposals:
        for case in proposal.cases:
            source = existing.get((proposal.experiment_key, case.case_key))
            anchors.append(
                {
                    "experiment_key": proposal.experiment_key,
                    "case_key": case.case_key,
                    "relative_path": None if source is None else source[0],
                    "locator": None if source is None else source[1],
                }
            )
    return {
        "schema_version": 2,
        "profile": MATERIALIZATION_CONTRACT_PROFILE,
        "entrypoint": None if base_project is None else base_project.entrypoint,
        "development_initialization_entrypoint": (
            None
            if base_project is None
            else base_project.development_initialization_entrypoint
        ),
        "case_anchors": anchors,
        "resource_limits": None if base_project is None else base_project.resource_limits.model_dump(mode="json"),
        "collect_generated_outputs": True,
    }


def declarations_template_json(
    experiment_plan: bytes, *, base_project: DeckProjectDraft | None = None
) -> bytes:
    return _pretty_json(
        declarations_template(experiment_plan, base_project=base_project)
    )


def materialize_deck_project(
    *,
    metadata: Mapping[str, object],
    declarations: Mapping[str, object],
    files: Sequence[Mapping[str, str]],
    experiment_plan: bytes,
    execution_capability: bytes,
    preflight_attestation: Mapping[str, object] | None = None,
) -> DeckProjectDraft:
    """Build one project without interpreting solver-language content."""

    deck_files = tuple(DeckFile.model_validate(item, strict=True) for item in files)
    source_sha = _source_tree_sha256(deck_files)
    findings: list[MaterializationFinding] = []
    try:
        declared = DeckSourceDeclarations.model_validate_json(
            json.dumps(declarations, ensure_ascii=False, allow_nan=False), strict=True
        )
    except ValidationError as error:
        for item in error.errors(include_url=False)[:64]:
            findings.append(
                _finding(
                    "missing_control_binding",
                    f"source declaration is incomplete: {item['msg']}",
                    expected="complete deck/declarations.json",
                    observed="/".join(str(part) for part in item["loc"]),
                    fix="Complete the solver-neutral declaration; do not alter plan values.",
                )
            )
        _raise(findings, source_sha)
    capability = SolverCapabilitySnapshot.model_validate_json(
        execution_capability, strict=True
    )
    portfolio = ExperimentPortfolio.model_validate_json(experiment_plan, strict=True)
    contents = {item.relative_path: item.content for item in deck_files}
    if capability.solver_kind not in {"sprocess", "sdevice"}:
        findings.append(
            _finding(
                "unsupported_syntax",
                "declared-source materialization requires a direct TCAD solver",
                expected="sprocess or sdevice",
                observed=capability.solver_kind,
                fix="Bind an active direct-solver capability.",
            )
        )
    for path in (
        declared.entrypoint,
        declared.development_initialization_entrypoint,
    ):
        if path is not None and path not in contents:
            findings.append(
                _finding(
                    "missing_requirement_realization",
                    "declared entrypoint is absent from the source tree",
                    path=path,
                    expected=path,
                    fix="Create the declared source file or correct declarations.json.",
                )
            )

    expected_cases = {
        (proposal.experiment_key, case.case_key)
        for proposal in portfolio.proposals
        for case in proposal.cases
    }
    actual_cases = {
        (item.experiment_key, item.case_key) for item in declared.case_anchors
    }
    if len(actual_cases) != len(declared.case_anchors):
        findings.append(
            _finding(
                "duplicate_control_anchor",
                "case declarations must be unique",
                fix="Keep one source anchor for each experiment/case pair.",
            )
        )
    for key in sorted(expected_cases - actual_cases):
        findings.append(
            _finding(
                "missing_control_binding",
                "planned case has no declared source anchor",
                experiment=key[0],
                case=key[1],
                expected=key[1],
                fix="Declare one exact source locator for the planned case.",
            )
        )
    for key in sorted(actual_cases - expected_cases):
        findings.append(
            _finding(
                "value_mismatch",
                "declared case is absent from the experiment plan",
                experiment=key[0],
                case=key[1],
                observed=key[1],
                fix="Remove the undeclared case anchor.",
            )
        )

    located: dict[tuple[str, str], tuple[DeclaredCaseAnchor, int, int, str]] = {}
    for anchor in declared.case_anchors:
        content = contents.get(anchor.relative_path)
        if content is None:
            findings.append(
                _finding(
                    "missing_requirement_realization",
                    "declared source-anchor file is absent",
                    experiment=anchor.experiment_key,
                    case=anchor.case_key,
                    path=anchor.relative_path,
                    fix="Create the declared source file or correct its path.",
                )
            )
            continue
        count = content.count(anchor.locator)
        if count != 1:
            findings.append(
                _finding(
                    "duplicate_control_anchor" if count > 1 else "missing_control_binding",
                    "declared source locator must occur exactly once",
                    experiment=anchor.experiment_key,
                    case=anchor.case_key,
                    path=anchor.relative_path,
                    expected="1 occurrence",
                    observed=f"{count} occurrences",
                    fix="Use a unique exact locator from the authored solver source.",
                )
            )
            continue
        before = content[: content.index(anchor.locator)]
        line_start = before.count("\n") + 1
        line_end = line_start + anchor.locator.count("\n")
        located[(anchor.experiment_key, anchor.case_key)] = (
            anchor,
            line_start,
            line_end,
            hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    if findings:
        _raise(findings, source_sha)

    bindings: list[CaseParameterBinding] = []
    for proposal in portfolio.proposals:
        contract = proposal.comparison_contract
        if contract is None:
            continue
        variables = tuple(
            item
            for item in contract.variables
            if deck_scoped_comparison_variable(item.scientific_path)
        )
        for variable in variables:
            for expectation in variable.expectations:
                resolved = located[(proposal.experiment_key, expectation.case_key)]
                anchor, line_start, line_end, digest = resolved
                bindings.append(
                    CaseParameterBinding(
                        experiment_key=proposal.experiment_key,
                        case_key=expectation.case_key,
                        variable_key=variable.variable_key,
                        scientific_path=variable.scientific_path,
                        realized_value=_value_text(expectation.value),
                        unit=variable.unit,
                        relative_path=anchor.relative_path,
                        locator=anchor.locator,
                        requirement_keys=(),
                        materialization_kind="control_generated",
                        source_sha256=digest,
                        source_line_start=line_start,
                        source_line_end=line_end,
                        derivation="plan_value_at_author_declared_case_anchor",
                    )
                )
            # A locator proves source presence, not physical implementation.

    limits = declared.resource_limits or _resource_limits(metadata)
    collect_generated = (
        declared.collect_generated_outputs
        if declared.collect_generated_outputs is not None
        else not declared.raw_outputs
    )
    declared_output_names = tuple(item.name for item in declared.raw_outputs)
    declared_output_paths = tuple(item.relative_path for item in declared.raw_outputs)
    if len(declared_output_names) != len(set(declared_output_names)):
        findings.append(
            _finding(
                "duplicate_control_anchor",
                "raw output declaration names must be unique",
                fix="Keep one declaration for each raw output name.",
            )
        )
    if len(declared_output_paths) != len(set(declared_output_paths)):
        findings.append(
            _finding(
                "duplicate_control_anchor",
                "raw output declaration paths must be unique",
                fix="Keep one declaration for each raw output path.",
            )
        )
    if collect_generated and declared.raw_outputs:
        findings.append(
            _finding(
                "duplicate_control_anchor",
                "generated-output collection does not use per-file raw output declarations",
                fix="Remove raw_outputs; generated files are discovered and hashed after execution.",
            )
        )
    process_log_path = ".scid-capture/solver_stdout.log"
    if "solver_log" in set(declared_output_names) or process_log_path in set(
        declared_output_paths
    ):
        findings.append(
            _finding(
                "duplicate_control_anchor",
                "raw output declaration conflicts with the control-owned process log",
                expected=f"name != solver_log and path != {process_log_path}",
                fix="Remove the duplicate declaration; process-log capture is automatic.",
            )
        )
    if findings:
        _raise(findings, source_sha)
    report = ProjectMaterializationReport(
        profile=MATERIALIZER_PROFILE,
        source_tree_sha256=source_sha,
        status="pass",
        generated_case_bindings=len(bindings),
        generated_parameter_bindings=0,
        generated_requirements=0,
    )
    preflight = (
        None
        if preflight_attestation is None
        else ProjectPreflightAttestation.model_validate(
            preflight_attestation, strict=True
        )
    )
    if preflight is not None and preflight.source_tree_sha256 != source_sha:
        preflight = None
    return DeckProjectDraft(
        tool_profile=capability.profile_id,
        solver_kind=capability.solver_kind,
        capability_sha256=capability.capability_sha256,
        files=deck_files,
        execution_plan=(portfolio if metadata.get("execution_plan") is not None else None),
        input_slots=tuple(metadata.get("input_slots", ())),
        entrypoint=declared.entrypoint,
        development_initialization_entrypoint=(
            declared.development_initialization_entrypoint
        ),
        arguments=tuple(metadata.get("arguments", ())),
        expected_outputs=(
            ProjectExpectedOutput(
                name="solver_log",
                relative_path=process_log_path,
                media_type="text/plain",
                max_bytes=min(limits.max_output_bytes, 64 * 1024 * 1024),
                capture="process_log",
            ),
            *(
                ProjectExpectedOutput(
                    name=item.name,
                    relative_path=item.relative_path,
                    media_type=item.media_type,
                    max_bytes=min(limits.max_output_bytes, 64 * 1024 * 1024),
                    capture="workspace_file",
                )
                for item in declared.raw_outputs
            ),
        ),
        collect_generated_outputs=collect_generated,
        parameter_bindings=(),
        case_parameter_bindings=tuple(bindings),
        case_anchors=declared.case_anchors,
        runtime_assertions=(),
        realization_manifest=(),
        materialization_report=report,
        preflight_attestation=preflight,
        resource_limits=limits,
    )


def _resource_limits(metadata: Mapping[str, object]) -> ProjectResourceLimits:
    raw = metadata.get("resource_limits")
    if isinstance(raw, Mapping):
        return ProjectResourceLimits.model_validate(raw, strict=True)
    raise ValueError("execution metadata must declare resource_limits, including total storage")


def _source_tree_sha256(files: Sequence[DeckFile]) -> str:
    digest = hashlib.sha256()
    for item in sorted(files, key=lambda value: value.relative_path):
        digest.update(item.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _value_text(value: object) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is float:
        return format(value, ".17g")
    return str(value)


def _finding(
    reason: str,
    message: str,
    *,
    experiment: str | None = None,
    case: str | None = None,
    variable: str | None = None,
    path: str | None = None,
    expected: str | None = None,
    observed: str | None = None,
    fix: str,
) -> MaterializationFinding:
    return MaterializationFinding(
        reason_code=reason,
        severity="error",
        message=message,
        experiment_key=experiment,
        case_key=case,
        variable_key=variable,
        source_path=path,
        expected=expected,
        observed=observed,
        suggested_fix_scope=fix,
    )


def _raise(findings: Sequence[MaterializationFinding], source_sha: str) -> None:
    raise ProjectMaterializationError(
        ProjectMaterializationReport(
            profile=MATERIALIZER_PROFILE,
            source_tree_sha256=source_sha,
            status="fail",
            generated_case_bindings=0,
            generated_parameter_bindings=0,
            generated_requirements=0,
            findings=tuple(findings),
        )
    )


def report_json(report: ProjectMaterializationReport) -> bytes:
    return _pretty_json(report.model_dump(mode="json"))


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


__all__ = [
    "DeckSourceDeclarations",
    "MATERIALIZATION_CONTRACT_PROFILE",
    "MATERIALIZER_PROFILE",
    "ProjectMaterializationError",
    "declarations_template",
    "declarations_template_json",
    "materialization_contract",
    "materialization_contract_json",
    "materialize_deck_project",
    "report_json",
]
