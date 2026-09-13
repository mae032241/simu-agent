"""Evidence-bound study validation and physical interpretation."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .common import ContractDiagnostic, Identifier, SchemaModel, canonical_json
from .validation import (
    HypothesisAssessment,
    RecommendedTaskMode,
    ValidationEvidence,
)


GateStatus = Literal[
    "pass", "fail", "inconclusive", "not_evaluable", "not_applicable"
]


class ScientificGateResult(SchemaModel):
    status: GateStatus
    summary: Annotated[str, Field(min_length=1, max_length=4096)]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    findings: Annotated[tuple[str, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _decisive_gate_has_evidence(self) -> ScientificGateResult:
        if self.status in {"pass", "fail"} and not self.evidence_keys:
            raise ValueError("passing or failing gate requires evidence_keys")
        return self


class ScientificGateSequence(SchemaModel):
    evidence_identity: ScientificGateResult
    implementation_fidelity: ScientificGateResult
    numerical_validity: ScientificGateResult
    control_equivalence: ScientificGateResult
    observation: ScientificGateResult
    physical_interpretation: ScientificGateResult

    @property
    def prerequisite_status(self) -> Literal["pass", "invalid"]:
        return (
            "pass"
            if all(
                item.status in {"pass", "not_applicable"}
                for item in (
                    self.evidence_identity,
                    self.implementation_fidelity,
                    self.numerical_validity,
                    self.control_equivalence,
                )
            )
            else "invalid"
        )

    @property
    def first_failed_gate(self) -> str | None:
        for name in (
            "evidence_identity",
            "implementation_fidelity",
            "numerical_validity",
            "control_equivalence",
        ):
            if getattr(self, name).status not in {"pass", "not_applicable"}:
                return name
        return None


class ObjectiveDiagnosisAssessment(SchemaModel):
    """A diagnosis of the approved objective, separate from numerical checks."""

    objective_key: Identifier
    status: Literal["pass", "fail", "inconclusive", "not_evaluable"]
    comparison_keys: Annotated[tuple[Identifier, ...], Field(max_length=256,
        description="Existing comparison keys from cited scoring records only. Leave empty for native calculations; cite their published files using evidence_keys.")] = ()
    summary: Annotated[str, Field(min_length=1, max_length=4096)]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _decisive_assessment_has_evidence(self) -> ObjectiveDiagnosisAssessment:
        if self.status in {"pass", "fail"} and not self.evidence_keys:
            from ...operation_contract import declared_violation
            raise declared_violation("passing or failing objective assessment requires evidence_keys", path="$.evidence_keys")
        return self


class CalculationAttemptReference(SchemaModel):
    manifest_alias: Identifier
    attempt_key: Identifier
    proof_kind: Literal["current", "recovery"] = "current"


_COMPUTED_RECORD_RULE = "computed record requires result and no reason"
_NONCOMPUTED_RECORD_RULE = "noncomputed record requires reason and no numeric result"
_SOURCE_CASE_PAIR_RULE = "source experiment_key and case_key must be declared together"


class CalculationRecord(SchemaModel):
    """Bounded, replayable calculation evidence; never a scientific verdict."""

    record_key: Identifier
    input_digests: Annotated[dict[str, str], Field(max_length=40)]
    request: dict[str, Any]
    algorithm_version: Annotated[str, Field(min_length=1, max_length=128)]
    status: Annotated[Literal["computed", "unavailable", "unsupported", "error"],
                      Field(description=f"{_COMPUTED_RECORD_RULE}; {_NONCOMPUTED_RECORD_RULE}.")]
    result: dict[str, Any] | None = None
    reason_code: Identifier | None = None
    attempt: CalculationAttemptReference | None = None
    diagnostics: tuple[ContractDiagnostic, ...] = Field(default=(), max_length=8)
    calculation_ref: Identifier | None = Field(default=None, exclude=True,
        description="Tool-returned evidence alias. Cite this alias in evidence; control retains the complete record. Optional transport hint, excluded from calculation identity.")

    @model_validator(mode="after")
    def _bounded_status(self) -> CalculationRecord:
        if len(canonical_json(self.model_dump(mode="json"))) > 32 * 1024:
            raise ValueError("calculation record exceeds 32 KiB")
        if self.status == "computed":
            if self.result is None or self.reason_code is not None:
                from ...operation_contract import declared_violation
                raise declared_violation(_COMPUTED_RECORD_RULE,
                    path="$.result" if self.result is None else "$.reason_code")
        elif self.result is not None or self.reason_code is None:
            from ...operation_contract import declared_violation
            raise declared_violation(_NONCOMPUTED_RECORD_RULE,
                path="$.reason_code" if self.reason_code is None else "$.result")
        return self


class CaseMappingEvidence(SchemaModel):
    input_alias: Identifier
    locator: Annotated[str, Field(min_length=1, max_length=256)]


class CaseMappingBasis(SchemaModel):
    kind: Literal["declared", "evidence"]
    evidence_refs: tuple[CaseMappingEvidence, ...] = Field(default=(), max_length=8)
    rationale: Annotated[str, Field(min_length=1, max_length=2048)]


class AnalysisSourceReference(SchemaModel):
    """Explicit evidence locator; bound identity is checked by the domain validator."""

    source_key: Identifier
    input_alias: Annotated[str, Field(min_length=1, max_length=256)]
    case_mapping_basis: CaseMappingBasis | None = None
    output_name: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    experiment_key: Identifier | None = Field(default=None, description=_SOURCE_CASE_PAIR_RULE)
    case_key: Identifier | None = Field(default=None, description=_SOURCE_CASE_PAIR_RULE)

    @model_validator(mode="after")
    def _case_identity_is_paired(self) -> AnalysisSourceReference:
        if (self.experiment_key is None) != (self.case_key is None):
            from ...operation_contract import declared_violation
            raise declared_violation(_SOURCE_CASE_PAIR_RULE,
                path="$.experiment_key" if self.experiment_key is None else "$.case_key")
        return self


class LayeredDiagnosisReport(SchemaModel):
    study_kind: Literal["scientific", "engineering"] = "scientific"
    experiment_key: Identifier
    plan_key: Identifier
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    evidence: Annotated[tuple[ValidationEvidence, ...], Field(max_length=256)] = ()
    source_references: Annotated[tuple[AnalysisSourceReference, ...], Field(max_length=64)] = ()
    gates: ScientificGateSequence | None = None
    overall_verdict: Literal["pass", "fail", "inconclusive", "invalid_study"]
    claim_allowed: bool
    objective_assessment: ObjectiveDiagnosisAssessment | None = None
    hypothesis_assessments: Annotated[
        tuple[HypothesisAssessment, ...], Field(max_length=32)
    ] = ()
    limitations: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    remaining_contradiction: Annotated[str, Field(min_length=1, max_length=8192)] | None = None
    next_action: Annotated[str, Field(min_length=1, max_length=4096)] | None = None
    recommended_task_mode: RecommendedTaskMode | None = None
    calculation_records: Annotated[tuple[CalculationRecord, ...], Field(max_length=8)] = Field(default=(),
        description="Legacy inline calculation records remain readable. For new tool results, cite calculation_ref in evidence instead; tools retain records and receipts automatically.")
    analysis_method: Annotated[str, Field(min_length=1, max_length=4096)] | None = None
    method_changes: Annotated[tuple[str, ...], Field(max_length=16)] = ()

    @model_validator(mode="after")
    def _references_and_bounds_are_consistent(self) -> LayeredDiagnosisReport:
        issues = diagnosis_consistency_issues(self)
        if issues:
            from ...operation_contract import SemanticRuleViolation, declared_violation
            # These messages and paths are emitted only by the mechanical checks below.
            details = tuple(detail for item in issues for detail in declared_violation(
                item["message"], path="$" + "".join(
                    f"[{part}]" if part.isdigit() else "." + part
                    for part in item["path"].split("/")[1:])).details)
            raise SemanticRuleViolation("; ".join(item["message"] for item in issues), details=details)
        return self


def diagnosis_consistency_issues(report: LayeredDiagnosisReport) -> tuple[dict[str, Any], ...]:
    """Return mechanical inconsistencies without deriving or rewriting science."""
    issues = []
    def issue(path, message, **suggestion):
        issues.append({"path": path, "message": message, **suggestion})
    record_keys = tuple(item.record_key for item in report.calculation_records)
    if len(record_keys) != len(set(record_keys)):
        issue("/calculation_records", "calculation record keys must be unique")
    if sum(len(canonical_json(item.model_dump(mode="json"))) for item in report.calculation_records) > 96 * 1024:
        issue("/calculation_records", "calculation records exceed report byte budget")
    assessment_keys = tuple(item.hypothesis_key for item in report.hypothesis_assessments)
    if len(assessment_keys) != len(set(assessment_keys)):
        issue("/hypothesis_assessments", "a diagnosis may assess each hypothesis once")
    return tuple(issues)


def validate_layered_diagnosis(value: dict[str, object]) -> dict[str, object]:
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")



__all__ = [
    "GateStatus",
    "LayeredDiagnosisReport",
    "ObjectiveDiagnosisAssessment",
    "ScientificGateResult",
    "ScientificGateSequence",
    "diagnosis_consistency_issues",
    "validate_layered_diagnosis",
]
