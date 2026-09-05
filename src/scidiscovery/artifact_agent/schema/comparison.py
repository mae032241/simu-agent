"""Deterministic comparison-contract checks over realized scientific cases."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, Sha256
from .experiment import ComparisonContract, ComparisonVariable
from .scientific_foundation import ScalarValue


class RealizedValue(SchemaModel):
    variable_key: Identifier
    scientific_path: Annotated[str, Field(min_length=1, max_length=4096)]
    value: ScalarValue
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    source_locator: Annotated[str, Field(min_length=1, max_length=4096)]


class RealizationSnapshot(SchemaModel):
    case_key: Identifier
    values: Annotated[tuple[RealizedValue, ...], Field(min_length=1, max_length=10000)]
    source_description: Annotated[str, Field(min_length=1, max_length=4096)]
    materialization_kind: Literal["control_materialized", "historical_qualified"]
    source_artifact_sha256s: Annotated[
        tuple[Sha256, ...], Field(min_length=1, max_length=4096)
    ]
    capability_sha256: Sha256

    @model_validator(mode="after")
    def _values_are_unambiguous(self) -> RealizationSnapshot:
        keys = tuple(item.variable_key for item in self.values)
        paths = tuple(item.scientific_path for item in self.values)
        if len(keys) != len(set(keys)):
            raise ValueError("realization variable_key values must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("realization scientific paths must be unique")
        if len(self.source_artifact_sha256s) != len(
            set(self.source_artifact_sha256s)
        ):
            raise ValueError("realization source artifact digests must be unique")
        return self


class ComparisonDifference(SchemaModel):
    comparison_case_key: Identifier
    variable_key: Identifier
    scientific_path: Annotated[str, Field(min_length=1, max_length=4096)]
    classification: Literal[
        "expected_change",
        "verified_invariant",
        "permitted_difference",
        "unexpected_difference",
        "missing_realization",
        "requires_review",
    ]
    status: Literal["pass", "fail", "inconclusive"]
    baseline_value: ScalarValue | None = None
    comparison_value: ScalarValue | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    baseline_source_locator: Annotated[
        str, Field(min_length=1, max_length=4096)
    ] | None = None
    comparison_source_locator: Annotated[
        str, Field(min_length=1, max_length=4096)
    ] | None = None
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class ControlEquivalenceReport(SchemaModel):
    baseline_case_key: Identifier
    comparison_case_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=10000)
    ]
    status: Literal["pass", "fail", "inconclusive"]
    physical_claim_evaluable: bool
    differences: Annotated[
        tuple[ComparisonDifference, ...], Field(min_length=1, max_length=100000)
    ]
    summary: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _status_is_derived(self) -> ControlEquivalenceReport:
        statuses = {item.status for item in self.differences}
        derived = "fail" if "fail" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
        if self.status != derived:
            raise ValueError("control-equivalence status does not match differences")
        if self.physical_claim_evaluable != (derived == "pass"):
            raise ValueError("physical claim is evaluable only after control equivalence passes")
        return self


class ExperimentControlEquivalenceReport(SchemaModel):
    experiment_key: Identifier
    realization_snapshot_sha256s: Annotated[
        tuple[Sha256, ...], Field(max_length=10000)
    ]
    report: ControlEquivalenceReport

    @model_validator(mode="after")
    def _snapshot_digests_are_unique(self) -> ExperimentControlEquivalenceReport:
        if len(self.realization_snapshot_sha256s) != len(
            set(self.realization_snapshot_sha256s)
        ):
            raise ValueError("experiment realization snapshot digests must be unique")
        if self.report.status == "pass" and len(self.realization_snapshot_sha256s) < 2:
            raise ValueError("passing experiment requires at least two snapshots")
        return self


class SingleCaseControlRealizationReport(SchemaModel):
    experiment_key: Identifier
    case_key: Identifier
    realization_snapshot_sha256: Sha256
    status: Literal["not_applicable"] = "not_applicable"
    physical_claim_evaluable: Literal[False] = False
    summary: Annotated[str, Field(min_length=1, max_length=4096)]


class StudyControlEquivalenceReport(SchemaModel):
    experiment_reports: Annotated[
        tuple[ExperimentControlEquivalenceReport, ...],
        Field(default=(), max_length=10000),
    ]
    single_case_reports: Annotated[
        tuple[SingleCaseControlRealizationReport, ...],
        Field(default=(), max_length=10000),
    ]
    status: Literal["pass", "fail", "inconclusive", "not_applicable"]
    physical_claim_evaluable: bool
    summary: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _status_is_derived(self) -> StudyControlEquivalenceReport:
        keys = tuple(item.experiment_key for item in self.experiment_reports)
        single_keys = tuple(item.experiment_key for item in self.single_case_reports)
        if not keys and not single_keys:
            raise ValueError("study control-equivalence report cannot be empty")
        if len(keys) != len(set(keys)) or len(single_keys) != len(set(single_keys)):
            raise ValueError("study control-equivalence experiment keys must be unique")
        if set(keys).intersection(single_keys):
            raise ValueError("study experiment cannot be both compared and single-case")
        statuses = {item.report.status for item in self.experiment_reports}
        derived = (
            "fail"
            if "fail" in statuses
            else "inconclusive"
            if "inconclusive" in statuses
            else "pass"
            if statuses
            else "not_applicable"
        )
        if self.status != derived:
            raise ValueError("study control-equivalence status is not derived")
        if self.physical_claim_evaluable != (derived == "pass"):
            raise ValueError(
                "study physical claim is evaluable only after every comparison passes"
            )
        return self


def _matches_expected(
    value: ScalarValue, expected: ScalarValue, variable: ComparisonVariable
) -> bool | None:
    if variable.equivalence_rule == "reviewed":
        return None
    if variable.equivalence_rule == "exact":
        return type(value) is type(expected) and value == expected
    assert variable.tolerance is not None
    if type(value) not in {int, float} or type(expected) not in {int, float}:
        return False
    return math.isclose(
        float(value), float(expected), rel_tol=0.0, abs_tol=variable.tolerance
    )


def evaluate_control_equivalence(
    contract: ComparisonContract,
    snapshots: tuple[RealizationSnapshot, ...],
    *,
    reviewed_variable_keys: frozenset[str] = frozenset(),
) -> ControlEquivalenceReport:
    """Compare realized cases without assigning any physical interpretation."""

    by_case = {item.case_key: item for item in snapshots}
    if len(by_case) != len(snapshots):
        raise ValueError("realization snapshots must have unique case_key values")
    expected_cases = {contract.baseline_case_key, *contract.comparison_case_keys}
    if set(by_case) != expected_cases:
        raise ValueError("snapshots must cover the exact comparison cases")
    values_by_case = {
        case_key: {item.variable_key: item for item in snapshot.values}
        for case_key, snapshot in by_case.items()
    }
    baseline_values = values_by_case[contract.baseline_case_key]
    declared = {item.variable_key: item for item in contract.variables}
    differences: list[ComparisonDifference] = []

    for comparison_case in contract.comparison_case_keys:
        comparison_values = values_by_case[comparison_case]
        for variable in contract.variables:
            expected = {
                item.case_key: item.value for item in variable.expectations
            }
            baseline = baseline_values.get(variable.variable_key)
            comparison = comparison_values.get(variable.variable_key)
            if baseline is None or comparison is None:
                differences.append(
                    ComparisonDifference(
                        comparison_case_key=comparison_case,
                        variable_key=variable.variable_key,
                        scientific_path=variable.scientific_path,
                        classification="missing_realization",
                        status="inconclusive",
                        baseline_value=None if baseline is None else baseline.value,
                        comparison_value=(
                            None if comparison is None else comparison.value
                        ),
                        unit=variable.unit,
                        baseline_source_locator=(
                            None if baseline is None else baseline.source_locator
                        ),
                        comparison_source_locator=(
                            None if comparison is None else comparison.source_locator
                        ),
                        rationale="A declared comparison variable is absent from the realized case.",
                    )
                )
                continue
            path_and_unit_match = (
                baseline.scientific_path == variable.scientific_path
                and comparison.scientific_path == variable.scientific_path
                and baseline.unit == variable.unit
                and comparison.unit == variable.unit
            )
            reviewed_match = (
                variable.equivalence_rule == "reviewed"
                and variable.variable_key in reviewed_variable_keys
            )
            baseline_match = (
                True
                if reviewed_match
                else _matches_expected(
                    baseline.value, expected[contract.baseline_case_key], variable
                )
            )
            comparison_match = (
                True
                if reviewed_match
                else _matches_expected(
                    comparison.value, expected[comparison_case], variable
                )
            )
            if baseline_match is None or comparison_match is None:
                classification = "requires_review"
                status = "inconclusive"
                rationale = "The comparison contract requires a reviewed equivalence judgment."
            elif not path_and_unit_match or not baseline_match or not comparison_match:
                classification = "unexpected_difference"
                status = "fail"
                rationale = "The realized path, unit, or value differs from the pre-registered contract."
            elif variable.comparison_role == "intended_change":
                classification = "expected_change"
                status = "pass"
                rationale = (
                    "The exact accepted independent review satisfies the reviewed equivalence "
                    "rule and the realized path and unit match the contract."
                    if reviewed_match
                    else "The intended variable change matches the contract."
                )
            elif variable.comparison_role == "frozen":
                classification = "verified_invariant"
                status = "pass"
                rationale = (
                    "The exact accepted independent review satisfies the reviewed equivalence "
                    "rule and the realized path and unit match the contract."
                    if reviewed_match
                    else "The declared invariant is identical and matches the contract."
                )
            else:
                classification = "permitted_difference"
                status = "pass"
                rationale = (
                    "The exact accepted independent review satisfies the reviewed equivalence "
                    "rule and the realized path and unit match the contract."
                    if reviewed_match
                    else "The declared permitted difference matches the contract."
                )
            differences.append(
                ComparisonDifference(
                    comparison_case_key=comparison_case,
                    variable_key=variable.variable_key,
                    scientific_path=variable.scientific_path,
                    classification=classification,
                    status=status,
                    baseline_value=baseline.value,
                    comparison_value=comparison.value,
                    unit=variable.unit,
                    baseline_source_locator=baseline.source_locator,
                    comparison_source_locator=comparison.source_locator,
                    rationale=rationale,
                )
            )

        extra_keys = (set(baseline_values) | set(comparison_values)) - set(declared)
        for key in sorted(extra_keys):
            baseline = baseline_values.get(key)
            comparison = comparison_values.get(key)
            if baseline is not None and comparison is not None and (
                baseline.scientific_path == comparison.scientific_path
                and baseline.unit == comparison.unit
                and type(baseline.value) is type(comparison.value)
                and baseline.value == comparison.value
            ):
                continue
            exemplar = baseline or comparison
            assert exemplar is not None
            differences.append(
                ComparisonDifference(
                    comparison_case_key=comparison_case,
                    variable_key=key,
                    scientific_path=exemplar.scientific_path,
                    classification="unexpected_difference",
                    status="fail",
                    baseline_value=None if baseline is None else baseline.value,
                    comparison_value=(
                        None if comparison is None else comparison.value
                    ),
                    unit=exemplar.unit,
                    baseline_source_locator=(
                        None if baseline is None else baseline.source_locator
                    ),
                    comparison_source_locator=(
                        None if comparison is None else comparison.source_locator
                    ),
                    rationale="An undeclared realized variable differs between compared cases.",
                )
            )

    statuses = {item.status for item in differences}
    status: Literal["pass", "fail", "inconclusive"] = (
        "fail" if "fail" in statuses else "inconclusive" if "inconclusive" in statuses else "pass"
    )
    return ControlEquivalenceReport(
        baseline_case_key=contract.baseline_case_key,
        comparison_case_keys=contract.comparison_case_keys,
        status=status,
        physical_claim_evaluable=status == "pass",
        differences=tuple(differences),
        summary=(
            "All declared changes and invariants match the comparison contract."
            if status == "pass"
            else "The realized cases are not yet a valid physical comparison."
        ),
    )


__all__ = [
    "ComparisonDifference",
    "ControlEquivalenceReport",
    "ExperimentControlEquivalenceReport",
    "RealizationSnapshot",
    "RealizedValue",
    "SingleCaseControlRealizationReport",
    "StudyControlEquivalenceReport",
    "evaluate_control_equivalence",
]
