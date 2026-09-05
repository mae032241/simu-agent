"""Deterministic, execution-free TCAD Artifact transformations."""

from __future__ import annotations

import json
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path
from typing import Mapping

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.comparison import (
    ComparisonDifference,
    ControlEquivalenceReport,
    ExperimentControlEquivalenceReport,
    RealizationSnapshot,
    RealizedValue,
    SingleCaseControlRealizationReport,
    StudyControlEquivalenceReport,
    evaluate_control_equivalence,
)
from scidiscovery.artifact_agent.schema.experiment import (
    ComparisonContract,
    ExperimentPortfolio,
)
from .execution_control import SolverCapabilitySnapshot
from .project_packager import (
    DeckProjectDraft,
    DeckReviewReport,
    ReviewedDeckPackage,
    TCADRuntimeManifest,
    attest_runtime_contract,
    deck_project_diff,
    deck_scoped_comparison_variable,
    validate_deck_review_against_project,
    validate_project_case_controls,
)
from .project_materializer import materialize_deck_project

def _process_log_capture_migration(
    reviewed: DeckProjectDraft, rematerialized: DeckProjectDraft
) -> bool:
    """Accept only the control-owned solver-log capture annotation migration."""

    reviewed_value = reviewed.model_dump(mode="json")
    rematerialized_value = rematerialized.model_dump(mode="json")
    reviewed_outputs = reviewed_value.get("expected_outputs")
    generated_outputs = rematerialized_value.get("expected_outputs")
    if (
        not isinstance(reviewed_outputs, list)
        or not isinstance(generated_outputs, list)
        or len(reviewed_outputs) != len(generated_outputs)
    ):
        return False
    migrated = False
    for old, new in zip(reviewed_outputs, generated_outputs, strict=True):
        if not isinstance(old, dict) or not isinstance(new, dict):
            return False
        if old.get("capture") == "workspace_file" and new.get("capture") == "process_log":
            old["capture"] = "process_log"
            migrated = True
    return migrated and reviewed_value == rematerialized_value


def compare_projects(inputs: Mapping[str, bytes]) -> dict[str, tuple[bytes, ...]]:
    if set(inputs) != {"base_project", "revised_project"}:
        raise ValueError(
            "TCAD deck comparison requires base_project and revised_project inputs"
        )
    base = DeckProjectDraft.model_validate_json(inputs["base_project"], strict=True)
    revised = DeckProjectDraft.model_validate_json(
        inputs["revised_project"], strict=True
    )
    difference = {
        "schema_version": 1,
        "base_project_sha256": canonical_sha256(base.model_dump(mode="json")),
        "revised_project_sha256": canonical_sha256(
            revised.model_dump(mode="json")
        ),
        **deck_project_diff(base, revised),
        "file_deltas": _file_deltas(base, revised),
    }
    return {"project_diff": (canonical_json(difference),)}


def validate_review_payload(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    if set(inputs) != {"project", "review"}:
        raise ValueError("TCAD deck review validation requires project and review")
    project = DeckProjectDraft.model_validate_json(inputs["project"], strict=True)
    review = DeckReviewReport.model_validate_json(inputs["review"], strict=True)
    validate_deck_review_against_project(project, review)
    result = {
        "schema_version": 1,
        "valid": True,
        "verdict": review.verdict,
        "execution_ready": review.execution_ready,
        "review_scope": "holistic_tcad_code_review",
        "materialization_profile": (
            None
            if project.materialization_report is None
            else project.materialization_report.profile
        ),
        "requirement_rows_used": project.materialization_report is None,
    }
    return {"review_attestation": (canonical_json(result),)}


def package_reviewed_project(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    base_inputs = {"project", "review", "capability", "experiment_plan"}
    if not base_inputs.issubset(inputs):
        raise ValueError(
            "reviewed deck package requires project, review, capability, "
            "and experiment_plan"
        )
    portfolio = ExperimentPortfolio.model_validate_json(
        inputs["experiment_plan"], strict=True
    )
    if set(inputs) != base_inputs:
        raise ValueError("reviewed deck package accepts only its exact TCAD inputs")
    project = DeckProjectDraft.model_validate_json(
        inputs["project"], strict=True
    )
    if project.materialization_report is None:
        raise ValueError(
            "reviewed deck package requires a control-materialized project"
        )
    if (
        project.preflight_attestation is None
        or not project.preflight_attestation.qualified
    ):
        raise ValueError(
            "reviewed deck package requires a source-bound passing preflight"
        )
    if project.materialization_report.profile.endswith("declared-source.v2"):
        metadata = project.model_dump(mode="json")
        files = metadata.pop("files")
        preflight = metadata.get("preflight_attestation")
        for generated in (
            "schema_version",
            "tool_profile",
            "solver_kind",
            "capability_sha256",
            "expected_outputs",
            "parameter_bindings",
            "case_parameter_bindings",
            "runtime_assertions",
            "realization_manifest",
            "materialization_report",
            "preflight_attestation",
        ):
            metadata.pop(generated, None)
        anchors: dict[tuple[str, str], dict[str, str]] = {}
        for item in project.case_parameter_bindings:
            anchors.setdefault(
                (item.experiment_key, item.case_key),
                {
                    "experiment_key": item.experiment_key,
                    "case_key": item.case_key,
                    "relative_path": item.relative_path,
                    "locator": item.locator,
                },
            )
        rematerialized = materialize_deck_project(
            metadata=metadata,
            declarations={
                "schema_version": 2,
                "profile": "tcad.project-declaration-contract.v2",
                "entrypoint": project.entrypoint,
                "development_initialization_entrypoint": (
                    project.development_initialization_entrypoint
                ),
                "case_anchors": list(anchors.values()),
                "raw_outputs": [
                    {
                        "name": item.name,
                        "relative_path": item.relative_path,
                        "media_type": item.media_type,
                    }
                    for item in project.expected_outputs
                    if item.capture == "workspace_file"
                    and item.name != "solver_log"
                    and item.relative_path
                    != f"{Path(project.entrypoint).stem}.log"
                ],
            },
            files=files,
            experiment_plan=inputs["experiment_plan"],
            execution_capability=inputs["capability"],
            preflight_attestation=preflight,
        )
        if rematerialized != project and not _process_log_capture_migration(
            project, rematerialized
        ):
            raise ValueError(
                "reviewed project differs from deterministic rematerialization"
            )
    else:
        # Historical v1 projects remain readable/packageable, but every new
        # author workspace upgrades through declared-source v2.
        rematerialized = project
    validate_project_case_controls(rematerialized, inputs["experiment_plan"])
    package = ReviewedDeckPackage(
        project=rematerialized,
        review=DeckReviewReport.model_validate_json(inputs["review"], strict=True),
        capability=SolverCapabilitySnapshot.model_validate_json(
            inputs["capability"], strict=True
        ),
    )
    return {
        "reviewed_package": (canonical_json(package.model_dump(mode="json")),)
    }


def attest_runtime(inputs: Mapping[str, bytes]) -> dict[str, tuple[bytes, ...]]:
    required = {"reviewed_package", "runtime_manifest"}
    output_labels = set(inputs) - required
    if not required.issubset(inputs) or any(
        not label.startswith("output__") for label in output_labels
    ):
        raise ValueError(
            "runtime attestation requires reviewed_package, runtime_manifest, "
            "and optional output__<name> payloads"
        )
    report = attest_runtime_contract(
        ReviewedDeckPackage.model_validate_json(
            inputs["reviewed_package"], strict=True
        ),
        TCADRuntimeManifest.model_validate_json(
            inputs["runtime_manifest"], strict=True
        ),
        output_payloads={
            label.removeprefix("output__"): inputs[label]
            for label in output_labels
        },
    )
    return {
        "runtime_attestation": (canonical_json(report.model_dump(mode="json")),)
    }


def materialize_realization_snapshot(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    if set(inputs) != {"comparison_contract", "reviewed_package", "case"}:
        raise ValueError(
            "realization materialization requires comparison_contract, "
            "reviewed_package, and case"
        )
    contract = ComparisonContract.model_validate_json(
        inputs["comparison_contract"], strict=True
    )
    reviewed = ReviewedDeckPackage.model_validate_json(
        inputs["reviewed_package"], strict=True
    )
    case_value = json.loads(inputs["case"])
    if (
        not isinstance(case_value, dict)
        or set(case_value) != {"schema_version", "case_key"}
        or case_value.get("schema_version") != 1
        or not isinstance(case_value.get("case_key"), str)
    ):
        raise ValueError("realization case binding is invalid")
    if canonical_json(case_value) != inputs["case"]:
        raise ValueError("realization case binding must use canonical JSON")
    snapshot = _materialize_realization(
        contract,
        reviewed,
        case_key=case_value["case_key"],
    )
    return {
        "realization_snapshot": (canonical_json(snapshot.model_dump(mode="json")),)
    }


def evaluate_control_equivalence_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    if "experiment_plan" not in inputs:
        raise ValueError("control equivalence requires experiment_plan")
    package_names = tuple(
        sorted(
            name
            for name in inputs
            if name == "reviewed_package" or name.startswith("reviewed_package__")
        )
    )
    if not package_names or set(inputs) != {"experiment_plan", *package_names}:
        raise ValueError(
            "control equivalence accepts experiment_plan and one or more "
            "reviewed_package inputs"
        )
    portfolio = ExperimentPortfolio.model_validate_json(
        inputs["experiment_plan"], strict=True
    )
    packages = {
        name: ReviewedDeckPackage.model_validate_json(inputs[name], strict=True)
        for name in package_names
    }
    reports: list[ExperimentControlEquivalenceReport] = []
    single_case_reports: list[SingleCaseControlRealizationReport] = []
    snapshots: list[RealizationSnapshot] = []
    audit_experiments: list[dict[str, object]] = []
    for proposal in portfolio.proposals:
        contract = proposal.comparison_contract
        if contract is None:
            case_key = proposal.cases[0].case_key
            candidates: dict[str, tuple[str, ReviewedDeckPackage]] = {}
            for input_name, reviewed in packages.items():
                declared_cases = {
                    item.case_key
                    for item in reviewed.project.case_parameter_bindings
                    if item.experiment_key == proposal.experiment_key
                }
                suffix = input_name.removeprefix("reviewed_package__")
                alias_matches = suffix in {
                    case_key,
                    f"{proposal.experiment_key}__{case_key}",
                }
                implicit_single = (
                    input_name == "reviewed_package"
                    and len(packages) == 1
                    and not declared_cases
                )
                if case_key in declared_cases or alias_matches or implicit_single:
                    digest = canonical_sha256(reviewed.model_dump(mode="json"))
                    candidates[digest] = (input_name, reviewed)
            if len(candidates) != 1:
                raise ValueError(
                    "single-case realization requires one unambiguous reviewed package"
                )
            _, (source_name, reviewed) = next(iter(candidates.items()))
            snapshot = _materialize_single_case(
                reviewed,
                experiment_key=proposal.experiment_key,
                case_key=case_key,
            )
            snapshots.append(snapshot)
            single_case_reports.append(
                SingleCaseControlRealizationReport(
                    experiment_key=proposal.experiment_key,
                    case_key=case_key,
                    realization_snapshot_sha256=canonical_sha256(snapshot),
                    summary=(
                        "The single case was materialized from one exact reviewed "
                        "package; control equivalence is not applicable."
                    ),
                )
            )
            audit_experiments.append(
                {
                    "experiment_key": proposal.experiment_key,
                    "case_sources": {case_key: source_name},
                    "missing_cases": [],
                    "mode": "single_case_materialization",
                }
            )
            continue
        deck_contract = _deck_scoped_contract(contract)
        expected_cases = {
            contract.baseline_case_key,
            *contract.comparison_case_keys,
        }
        coverage: dict[
            str, list[tuple[str, str, ReviewedDeckPackage, frozenset[str]]]
        ] = {case_key: [] for case_key in expected_cases}
        for input_name, reviewed in packages.items():
            covered = _package_case_coverage(
                input_name,
                reviewed,
                experiment_key=proposal.experiment_key,
                expected_cases=expected_cases,
                only_contract=len(
                    tuple(
                        item
                        for item in portfolio.proposals
                        if item.comparison_contract is not None
                    )
                )
                == 1,
            )
            package_digest = canonical_sha256(reviewed.model_dump(mode="json"))
            for case_key in covered:
                coverage[case_key].append(
                    (
                        package_digest,
                        input_name,
                        reviewed,
                        frozenset(covered),
                    )
                )
        selected: dict[
            str, tuple[str, str, ReviewedDeckPackage, frozenset[str]]
        ] = {}
        conflicts: list[str] = []
        for case_key, candidates in coverage.items():
            by_digest = {item[0]: item for item in candidates}
            if len(by_digest) > 1:
                conflicts.append(case_key)
            elif by_digest:
                selected[case_key] = next(iter(by_digest.values()))
        if conflicts:
            raise ValueError(
                "control equivalence has conflicting package sources for cases: "
                + ", ".join(sorted(conflicts))
            )
        missing_cases = sorted(expected_cases - set(selected))
        experiment_snapshots: list[RealizationSnapshot] = []
        if missing_cases:
            report = _missing_case_report(deck_contract, missing_cases)
        else:
            for case_key in (
                deck_contract.baseline_case_key,
                *deck_contract.comparison_case_keys,
            ):
                _, _, reviewed, package_coverage = selected[case_key]
                snapshot = _materialize_realization(
                    deck_contract,
                    reviewed,
                    case_key=case_key,
                    experiment_key=proposal.experiment_key,
                    allow_missing=True,
                    allow_global_case_values=package_coverage == {case_key},
                )
                experiment_snapshots.append(snapshot)
            report = evaluate_control_equivalence(
                deck_contract,
                tuple(experiment_snapshots),
                reviewed_variable_keys=frozenset(
                    item.variable_key
                    for item in deck_contract.variables
                    if item.equivalence_rule == "reviewed"
                ),
            )
        snapshots.extend(experiment_snapshots)
        snapshot_hashes = tuple(
            canonical_sha256(item) for item in experiment_snapshots
        )
        reports.append(
            ExperimentControlEquivalenceReport(
                experiment_key=proposal.experiment_key,
                realization_snapshot_sha256s=snapshot_hashes,
                report=report,
            )
        )
        audit_experiments.append(
            {
                "experiment_key": proposal.experiment_key,
                "case_sources": {
                    case_key: (
                        None
                        if case_key not in selected
                        else selected[case_key][1]
                    )
                    for case_key in sorted(expected_cases)
                },
                "missing_cases": missing_cases,
            }
        )
    statuses = {item.report.status for item in reports}
    status = (
        "fail"
        if "fail" in statuses
        else "inconclusive"
        if "inconclusive" in statuses
        else "pass"
        if statuses
        else "not_applicable"
    )
    study = StudyControlEquivalenceReport(
        experiment_reports=tuple(reports),
        single_case_reports=tuple(single_case_reports),
        status=status,
        physical_claim_evaluable=status == "pass",
        summary=(
            "Every realized comparison matches its pre-registered control contract."
            if status == "pass"
            else "Every declared single case was materialized; no comparison "
            "contract applies."
            if status == "not_applicable"
            else "One or more realized comparisons are not claim-evaluable."
        ),
    )
    return {
        "control_equivalence": (study.canonical_json(),),
        "realization_snapshots": tuple(
            snapshot.canonical_json() for snapshot in snapshots
        ),
        "control_audit": (
            canonical_json(
                {
                    "schema_version": 1,
                    "experiments": audit_experiments,
                }
            ),
        ),
    }


def _deck_scoped_contract(contract: ComparisonContract) -> ComparisonContract:
    """Project only the controls whose realization belongs to solver code.

    Scorer, reference-input, analysis, and diagnosis controls are verified by
    their respective deterministic transforms after execution.  Including
    them in deck control equivalence would turn an intentionally absent deck
    binding into a false implementation defect.
    """

    variables = tuple(
        item
        for item in contract.variables
        if deck_scoped_comparison_variable(item.scientific_path)
    )
    if not variables:
        raise ValueError(
            "comparison contract has no deck-scoped variables for TCAD control "
            "equivalence"
        )
    return contract.model_copy(update={"variables": variables})


def _package_case_coverage(
    input_name: str,
    reviewed: ReviewedDeckPackage,
    *,
    experiment_key: str,
    expected_cases: set[str],
    only_contract: bool,
) -> set[str]:
    declared = {
        item.case_key
        for item in reviewed.project.case_parameter_bindings
        if item.experiment_key == experiment_key
    }
    if declared:
        return declared & expected_cases
    if input_name == "reviewed_package":
        return set()
    suffix = input_name.removeprefix("reviewed_package__")
    scoped_prefix = experiment_key + "__"
    if suffix.startswith(scoped_prefix):
        candidate = suffix.removeprefix(scoped_prefix)
        return {candidate} if candidate in expected_cases else set()
    if only_contract and suffix in expected_cases:
        return {suffix}
    return set()


def _missing_case_report(
    contract: ComparisonContract, missing_cases: list[str]
) -> ControlEquivalenceReport:
    differences = tuple(
        ComparisonDifference(
            comparison_case_key=comparison_case,
            variable_key=variable.variable_key,
            scientific_path=variable.scientific_path,
            classification="missing_realization",
            status="inconclusive",
            unit=variable.unit,
            rationale=(
                "A required case has no unambiguous reviewed-package source: "
                + ", ".join(missing_cases)
            ),
        )
        for comparison_case in contract.comparison_case_keys
        for variable in contract.variables
        if deck_scoped_comparison_variable(variable.scientific_path)
    )
    return ControlEquivalenceReport(
        baseline_case_key=contract.baseline_case_key,
        comparison_case_keys=contract.comparison_case_keys,
        status="inconclusive",
        physical_claim_evaluable=False,
        differences=differences,
        summary="Required case realization sources are missing.",
    )


def _materialize_single_case(
    reviewed: ReviewedDeckPackage,
    *,
    experiment_key: str,
    case_key: str,
) -> RealizationSnapshot:
    project = reviewed.project
    scoped = tuple(
        item
        for item in project.case_parameter_bindings
        if item.experiment_key == experiment_key and item.case_key == case_key
    )
    scoped_keys = {item.variable_key for item in scoped}
    values: list[RealizedValue] = []
    for binding in scoped:
        _validate_bound_source_value(
            project,
            relative_path=binding.relative_path,
            locator=binding.locator,
            raw_value=binding.realized_value,
            variable_key=binding.variable_key,
            control_generated=binding.materialization_kind == "control_generated",
        )
        values.append(
            RealizedValue(
                variable_key=binding.variable_key,
                scientific_path=binding.scientific_path,
                value=binding.realized_value,
                unit=binding.unit,
                source_locator=f"{binding.relative_path}:{binding.locator}",
            )
        )
    for binding in project.parameter_bindings:
        if binding.name in scoped_keys:
            continue
        _validate_bound_source_value(
            project,
            relative_path=binding.relative_path,
            locator=binding.locator,
            raw_value=binding.declared_value,
            variable_key=binding.name,
            control_generated=binding.materialization_kind == "control_generated",
        )
        values.append(
            RealizedValue(
                variable_key=binding.name,
                scientific_path=f"implementation.parameters.{binding.name}",
                value=binding.declared_value,
                unit=binding.unit,
                source_locator=f"{binding.relative_path}:{binding.locator}",
            )
        )
    for deck_file in project.files:
        path_digest = sha256(deck_file.relative_path.encode("utf-8")).hexdigest()
        values.append(
            RealizedValue(
                variable_key=f"file_contract_{path_digest}",
                scientific_path=f"implementation.files.{deck_file.relative_path}",
                value=sha256(deck_file.content.encode("utf-8")).hexdigest(),
                unit="sha256",
                source_locator=deck_file.relative_path,
            )
        )
    values.extend(_implementation_contract_values(reviewed))
    return RealizationSnapshot(
        case_key=case_key,
        values=tuple(values),
        source_description=(
            "Single-case controls materialized from one exact reviewed deck package; "
            "no comparison status was inferred."
        ),
        materialization_kind="control_materialized",
        source_artifact_sha256s=(
            canonical_sha256(reviewed.model_dump(mode="json")),
            canonical_sha256(
                {
                    "schema_version": 1,
                    "experiment_key": experiment_key,
                    "case_key": case_key,
                }
            ),
        ),
        capability_sha256=reviewed.capability.capability_sha256,
    )


def _materialize_realization(
    contract: ComparisonContract,
    reviewed: ReviewedDeckPackage,
    *,
    case_key: str,
    experiment_key: str | None = None,
    allow_missing: bool = False,
    allow_global_case_values: bool = True,
) -> RealizationSnapshot:
    expected_cases = {contract.baseline_case_key, *contract.comparison_case_keys}
    if case_key not in expected_cases:
        raise ValueError("realization case is absent from the comparison contract")
    project = reviewed.project
    bindings = {item.name: item for item in project.parameter_bindings}
    case_bindings = {
        item.variable_key: item
        for item in project.case_parameter_bindings
        if item.case_key == case_key
        and (experiment_key is None or item.experiment_key == experiment_key)
    }
    declared = {
        item.variable_key: item
        for item in contract.variables
        if deck_scoped_comparison_variable(item.scientific_path)
    }

    values: list[RealizedValue] = []
    normalizable_locators: dict[str, list[tuple[str, str]]] = {}
    missing: list[str] = []
    for variable in contract.variables:
        if not deck_scoped_comparison_variable(variable.scientific_path):
            continue
        expected = next(
            item.value for item in variable.expectations if item.case_key == case_key
        )
        case_binding = case_bindings.get(variable.variable_key)
        global_binding = bindings.get(variable.variable_key)
        global_is_shared_frozen = (
            variable.comparison_role == "frozen"
            and len({item.value for item in variable.expectations}) == 1
        )
        if case_binding is not None:
            raw_value = case_binding.realized_value
            unit = case_binding.unit
            scientific_path = case_binding.scientific_path
            relative_path = case_binding.relative_path
            locator = case_binding.locator
            control_generated = (
                case_binding.materialization_kind == "control_generated"
            )
        elif global_binding is not None and (
            experiment_key is None
            or allow_global_case_values
            or global_is_shared_frozen
        ):
            raw_value = global_binding.declared_value
            unit = global_binding.unit
            scientific_path = variable.scientific_path
            relative_path = global_binding.relative_path
            locator = global_binding.locator
            control_generated = (
                global_binding.materialization_kind == "control_generated"
            )
        else:
            missing.append(variable.variable_key)
            continue
        _validate_bound_source_value(
            project,
            relative_path=relative_path,
            locator=locator,
            raw_value=raw_value,
            variable_key=variable.variable_key,
            control_generated=control_generated,
        )
        if experiment_key is None and unit != variable.unit:
            raise ValueError(
                f"comparison binding unit differs for {variable.variable_key}"
            )
        value = _parse_declared_value(raw_value, expected)
        values.append(
            RealizedValue(
                variable_key=variable.variable_key,
                scientific_path=scientific_path,
                value=value,
                unit=unit,
                source_locator=f"{relative_path}:{locator}",
            )
        )
        if variable.comparison_role != "frozen":
            normalizable_locators.setdefault(relative_path, []).append(
                (locator, variable.variable_key)
            )
    if missing and not allow_missing:
        raise ValueError(
            "reviewed project lacks comparison parameter bindings: "
            + ", ".join(sorted(missing))
        )
    if experiment_key is not None:
        for binding in project.case_parameter_bindings:
            variable = declared.get(binding.variable_key)
            if (
                binding.experiment_key == experiment_key
                and variable is not None
                and variable.comparison_role != "frozen"
            ):
                item = (binding.locator, binding.variable_key)
                locators = normalizable_locators.setdefault(
                    binding.relative_path, []
                )
                if item not in locators:
                    locators.append(item)

    for binding in project.parameter_bindings:
        if binding.name in declared or binding.name in case_bindings:
            continue
        values.append(
            RealizedValue(
                variable_key=binding.name,
                scientific_path=f"implementation.parameters.{binding.name}",
                value=binding.declared_value,
                unit=binding.unit,
                source_locator=f"{binding.relative_path}:{binding.locator}",
            )
        )
    for binding in project.case_parameter_bindings:
        if (
            binding.case_key != case_key
            or (experiment_key is not None and binding.experiment_key != experiment_key)
            or binding.variable_key in declared
        ):
            continue
        values.append(
            RealizedValue(
                variable_key=binding.variable_key,
                scientific_path=binding.scientific_path,
                value=binding.realized_value,
                unit=binding.unit,
                source_locator=f"{binding.relative_path}:{binding.locator}",
            )
        )

    for deck_file in project.files:
        normalized = deck_file.content
        for locator, variable_key in normalizable_locators.get(
            deck_file.relative_path, ()
        ):
            normalized = normalized.replace(locator, f"<declared:{variable_key}>")
        path_digest = sha256(deck_file.relative_path.encode("utf-8")).hexdigest()
        values.append(
            RealizedValue(
                variable_key=f"file_contract_{path_digest}",
                scientific_path=f"implementation.files.{deck_file.relative_path}",
                value=sha256(normalized.encode("utf-8")).hexdigest(),
                unit="sha256",
                source_locator=deck_file.relative_path,
            )
        )

    values.extend(_implementation_contract_values(reviewed))
    case_identity: dict[str, object] = {"schema_version": 1, "case_key": case_key}
    if experiment_key is not None:
        case_identity["experiment_key"] = experiment_key
    source_hashes = (
        canonical_sha256(contract),
        canonical_sha256(reviewed.model_dump(mode="json")),
        canonical_sha256(case_identity),
    )
    return RealizationSnapshot(
        case_key=case_key,
        values=tuple(values),
        source_description=(
            "Control-materialized from an exact comparison contract and reviewed "
            "deck package."
        ),
        materialization_kind="control_materialized",
        source_artifact_sha256s=source_hashes,
        capability_sha256=reviewed.capability.capability_sha256,
    )


def _validate_bound_source_value(
    project: DeckProjectDraft,
    *,
    relative_path: str,
    locator: str,
    raw_value: str,
    variable_key: str,
    control_generated: bool = False,
) -> None:
    source = next(
        item.content for item in project.files if item.relative_path == relative_path
    )
    if source.count(locator) != 1:
        raise ValueError(
            f"comparison binding locator is not unique for {variable_key}"
        )
    if not control_generated and raw_value not in locator:
        raise ValueError(
            "comparison binding value is not present in its exact locator for "
            f"{variable_key}"
        )


def _implementation_contract_values(
    reviewed: ReviewedDeckPackage,
) -> tuple[RealizedValue, ...]:
    project = reviewed.project
    capability = reviewed.capability
    return (
        _contract_value(
            "solver_kind_contract",
            "implementation.capability.solver_kind",
            capability.solver_kind,
            f"capability:{capability.profile_id}",
        ),
        _contract_value(
            "tool_profile_contract",
            "implementation.capability.profile_id",
            capability.profile_id,
            f"capability:{capability.profile_id}",
        ),
        _contract_value(
            "capability_digest_contract",
            "implementation.capability.sha256",
            capability.capability_sha256,
            f"capability:{capability.profile_id}",
            unit="sha256",
        ),
        _contract_value(
            "entrypoint_contract",
            "implementation.execution.entrypoint",
            project.entrypoint,
            "reviewed_project:entrypoint",
        ),
        _contract_value(
            "arguments_contract",
            "implementation.execution.arguments",
            canonical_json(project.arguments).decode("utf-8"),
            "reviewed_project:arguments",
        ),
        _contract_value(
            "resource_limits_contract",
            "implementation.execution.resource_limits",
            canonical_sha256(project.resource_limits.model_dump(mode="json")),
            "reviewed_project:resource_limits",
            unit="sha256",
        ),
        _contract_value(
            "expected_outputs_contract",
            "implementation.execution.expected_outputs",
            canonical_sha256(
                [item.model_dump(mode="json") for item in project.expected_outputs]
            ),
            "reviewed_project:expected_outputs",
            unit="sha256",
        ),
    )


def _parse_declared_value(raw: str, exemplar: object) -> object:
    if type(exemplar) is bool:
        if raw not in {"true", "false"}:
            raise ValueError("boolean comparison binding must use true or false")
        return raw == "true"
    if type(exemplar) is int:
        try:
            return int(raw)
        except ValueError as error:
            raise ValueError("integer comparison binding is invalid") from error
    if type(exemplar) is float:
        try:
            return float(raw)
        except ValueError as error:
            raise ValueError("numeric comparison binding is invalid") from error
    return raw


def _contract_value(
    variable_key: str,
    scientific_path: str,
    value: object,
    source_locator: str,
    *,
    unit: str = "categorical",
) -> RealizedValue:
    return RealizedValue(
        variable_key=variable_key,
        scientific_path=scientific_path,
        value=value,
        unit=unit,
        source_locator=source_locator,
    )


__all__ = [
    "attest_runtime",
    "compare_projects",
    "evaluate_control_equivalence_outputs",
    "materialize_realization_snapshot",
    "package_reviewed_project",
    "validate_review_payload",
]


def _file_deltas(
    base: DeckProjectDraft, revised: DeckProjectDraft
) -> tuple[dict[str, object], ...]:
    base_files = {item.relative_path: item.content for item in base.files}
    revised_files = {item.relative_path: item.content for item in revised.files}
    deltas: list[dict[str, object]] = []
    for path in sorted(set(base_files) | set(revised_files)):
        before = base_files.get(path)
        after = revised_files.get(path)
        if before == after:
            continue
        rendered = "".join(
            unified_diff(
                [] if before is None else before.splitlines(keepends=True),
                [] if after is None else after.splitlines(keepends=True),
                fromfile=f"base/{path}",
                tofile=f"revised/{path}",
                n=3,
            )
        )
        deltas.append(
            {
                "relative_path": path,
                "base_sha256": None
                if before is None
                else sha256(before.encode("utf-8")).hexdigest(),
                "revised_sha256": None
                if after is None
                else sha256(after.encode("utf-8")).hexdigest(),
                "unified_diff": rendered,
            }
        )
    return tuple(deltas)
