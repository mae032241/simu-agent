"""One deterministic claim projection for supported diagnosis schemas."""

from __future__ import annotations

from typing import Literal

from .common import Identifier, SchemaModel
from .layered_diagnosis import LayeredDiagnosisReport
from .validation import ValidationReport


class ClaimDecision(SchemaModel):
    report_kind: Literal["validation_report", "layered_diagnosis"]
    experiment_key: Identifier
    plan_key: Identifier
    overall_verdict: Literal["pass", "fail", "inconclusive", "invalid_study"]
    numerical_verdict: Literal[
        "pass", "fail", "inconclusive", "not_evaluable", "not_applicable"
    ]
    claim_allowed: bool


def project_claim_decision(
    report: ValidationReport | LayeredDiagnosisReport,
) -> ClaimDecision:
    if isinstance(report, LayeredDiagnosisReport):
        report_kind = "layered_diagnosis"
        numerical_verdict = report.gates.numerical_validity.status
    else:
        report_kind = "validation_report"
        numerical_verdict = report.numerical.status
    return ClaimDecision(
        report_kind=report_kind,
        experiment_key=report.experiment_key,
        plan_key=report.plan_key,
        overall_verdict=report.overall_verdict,
        numerical_verdict=numerical_verdict,
        claim_allowed=report.claim_allowed,
    )


__all__ = ["ClaimDecision", "project_claim_decision"]
