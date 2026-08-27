"""Causally ordered study validation and physical interpretation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json, canonical_sha256
from .curve_analysis import (
    CurveErrorAnalysisReport,
    analyze_curve_error,
    failed_residual_analysis_available,
)
from .curve_score import CurveBundle, CurveConsistencyReport
from .experiment import (
    ExperimentPortfolio,
    deterministic_validation_check_keys,
)
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
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise ValueError("gate evidence_keys must be unique")
        return self


class ScientificGateSequence(SchemaModel):
    evidence_identity: ScientificGateResult
    implementation_fidelity: ScientificGateResult
    numerical_validity: ScientificGateResult
    control_equivalence: ScientificGateResult
    observation: ScientificGateResult
    physical_interpretation: ScientificGateResult

    @model_validator(mode="after")
    def _causal_order_is_respected(self) -> ScientificGateSequence:
        prerequisites = (
            ("evidence_identity", self.evidence_identity),
            ("implementation_fidelity", self.implementation_fidelity),
            ("numerical_validity", self.numerical_validity),
            ("control_equivalence", self.control_equivalence),
        )
        blocked = False
        for name, gate in prerequisites:
            if blocked and gate.status != "not_evaluable":
                raise ValueError("downstream prerequisite gate must be not_evaluable")
            if gate.status in {"fail", "inconclusive", "not_evaluable"}:
                blocked = True
        if blocked:
            if self.observation.status != "not_evaluable":
                raise ValueError("observation must be not_evaluable after a failed prerequisite")
            if self.physical_interpretation.status != "not_evaluable":
                raise ValueError(
                    "physical interpretation must be not_evaluable after a failed prerequisite"
                )
        return self

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
    comparison_keys: Annotated[tuple[Identifier, ...], Field(max_length=256)] = ()
    summary: Annotated[str, Field(min_length=1, max_length=4096)]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _references_are_unique(self) -> ObjectiveDiagnosisAssessment:
        if len(self.comparison_keys) != len(set(self.comparison_keys)):
            raise ValueError("objective assessment comparison_keys must be unique")
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise ValueError("objective assessment evidence_keys must be unique")
        return self


class LayeredDiagnosisReport(SchemaModel):
    study_kind: Literal["scientific", "engineering"] = "scientific"
    experiment_key: Identifier
    plan_key: Identifier
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    evidence: Annotated[tuple[ValidationEvidence, ...], Field(max_length=256)] = ()
    gates: ScientificGateSequence
    overall_verdict: Literal["pass", "fail", "inconclusive", "invalid_study"]
    claim_allowed: bool
    objective_assessment: ObjectiveDiagnosisAssessment | None = None
    hypothesis_assessments: Annotated[
        tuple[HypothesisAssessment, ...], Field(max_length=32)
    ] = ()
    curve_analysis: CurveErrorAnalysisReport | None = None
    remaining_contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    recommended_task_mode: RecommendedTaskMode
    next_action: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _verdict_and_assessments_follow_the_gates(self) -> LayeredDiagnosisReport:
        source_keys = tuple(item.source_key for item in self.evidence)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("diagnosis evidence source_key values must be unique")
        known = set(source_keys)
        gate_results = (
            self.gates.evidence_identity,
            self.gates.implementation_fidelity,
            self.gates.numerical_validity,
            self.gates.control_equivalence,
            self.gates.observation,
            self.gates.physical_interpretation,
        )
        for gate in gate_results:
            if not set(gate.evidence_keys).issubset(known):
                raise ValueError("diagnosis gate references undeclared evidence")
        if self.objective_assessment is not None:
            if not set(self.objective_assessment.evidence_keys).issubset(known):
                raise ValueError(
                    "objective assessment references undeclared evidence"
                )
            expected_objective_status = (
                "not_evaluable"
                if self.gates.prerequisite_status == "invalid"
                else self.gates.observation.status
            )
            if self.objective_assessment.status != expected_objective_status:
                raise ValueError(
                    "objective assessment status must match the ordered objective gate"
                )
        if self.study_kind == "scientific":
            required = (
                self.gates.evidence_identity,
                self.gates.implementation_fidelity,
                self.gates.numerical_validity,
                self.gates.control_equivalence,
                self.gates.observation,
                self.gates.physical_interpretation,
            )
            if any(item.status == "not_applicable" for item in required):
                raise ValueError("scientific diagnosis cannot skip a required gate")
        elif self.hypothesis_assessments:
            raise ValueError("engineering diagnosis cannot assess physical hypotheses")

        if self.gates.prerequisite_status == "invalid":
            derived = "invalid_study"
        else:
            active_results = {
                item.status
                for item in (
                    self.gates.observation,
                    self.gates.physical_interpretation,
                )
                if item.status != "not_applicable"
            }
            if "fail" in active_results:
                derived = "fail"
            elif active_results == {"pass"}:
                derived = "pass"
            else:
                derived = "inconclusive"
        if self.overall_verdict != derived:
            raise ValueError("overall verdict does not match the ordered scientific gates")
        expected_claim = (
            self.study_kind == "scientific"
            and derived == "pass"
            and (
                self.objective_assessment is None
                or self.objective_assessment.status == "pass"
            )
        )
        if self.claim_allowed != expected_claim:
            raise ValueError(
                "claim_allowed is true only for a passing scientific study"
            )

        assessment_keys = tuple(
            item.hypothesis_key for item in self.hypothesis_assessments
        )
        if len(assessment_keys) != len(set(assessment_keys)):
            raise ValueError("a diagnosis may assess each hypothesis once")
        for assessment in self.hypothesis_assessments:
            if not set(assessment.evidence_keys).issubset(known):
                raise ValueError("hypothesis assessment references undeclared evidence")
            if derived == "invalid_study" and assessment.outcome not in {
                "invalid_study",
                "not_tested",
            }:
                raise ValueError("invalid study cannot support or contradict a hypothesis")
            if derived != "invalid_study" and assessment.outcome == "invalid_study":
                raise ValueError("valid study cannot be assessed as invalid_study")
            if assessment.outcome == "supports" and (
                derived != "pass"
                or self.gates.physical_interpretation.status != "pass"
            ):
                raise ValueError("support requires a valid passing physical interpretation")
            if assessment.outcome == "contradicts" and (
                derived != "fail"
                or self.gates.physical_interpretation.status != "fail"
            ):
                raise ValueError("contradiction requires a valid failed physical interpretation")
        return self


def validate_layered_diagnosis(value: dict[str, object]) -> dict[str, object]:
    return LayeredDiagnosisReport.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_tcad_diagnosis_task_output(
    value: dict[str, object],
    inputs: dict[str, bytes],
    handoff: dict[str, object],
) -> None:
    """Require exact validation-plan coverage before formal TCAD diagnosis."""

    del handoff
    diagnosis = LayeredDiagnosisReport.model_validate_json(
        canonical_json(value), strict=True
    )
    if "experiment_plan" not in inputs:
        return
    if set(inputs) not in (
        {"experiment_plan", "metric_report"},
        {"experiment_plan", "metric_report", "curve_bundle"},
    ):
        raise ValueError(
            "TCAD diagnosis coverage validation requires experiment_plan, "
            "metric_report, and at most curve_bundle"
        )
    portfolio = ExperimentPortfolio.model_validate_json(
        inputs["experiment_plan"], strict=True
    )
    metric_report = CurveConsistencyReport.model_validate_json(
        inputs["metric_report"], strict=True
    )
    if portfolio.objective_key is None:
        if diagnosis.objective_assessment is not None:
            raise ValueError(
                "objective_assessment is not admissible without plan objective_key"
            )
    else:
        assessment = diagnosis.objective_assessment
        if assessment is None:
            raise ValueError(
                "objective plan requires an explicit objective_assessment"
            )
        if assessment.objective_key != portfolio.objective_key:
            raise ValueError(
                "objective_assessment does not match the experiment objective_key"
            )
        objective_comparisons = tuple(
            item
            for item in metric_report.comparisons
            if item.gate_scope == "objective" and item.purpose == "target_fit"
        )
        expected_keys = tuple(item.comparison_key for item in objective_comparisons)
        if assessment.comparison_keys != expected_keys:
            raise ValueError(
                "objective_assessment must name the exact target-fit comparisons"
            )
        if diagnosis.gates.prerequisite_status == "invalid":
            expected_status = "not_evaluable"
        else:
            statuses = {item.status for item in objective_comparisons if item.required}
            expected_status = (
                "fail"
                if "fail" in statuses
                else "inconclusive"
                if not statuses or statuses & {"unavailable", "inconclusive"}
                else "pass"
            )
        if assessment.status != expected_status:
            raise ValueError(
                "objective assessment status differs from exact target-fit metrics"
            )
    plans = tuple(
        plan
        for plan in portfolio.validation_plans
        if plan.experiment_key == diagnosis.experiment_key
        and plan.plan_key == diagnosis.plan_key
    )
    if len(plans) != 1:
        raise ValueError("diagnosis does not name one exact experiment validation plan")
    plan = plans[0]
    expected_keys = deterministic_validation_check_keys(plan)
    if metric_report.validation_scope != "complete_plan":
        raise ValueError("TCAD diagnosis requires a complete-plan metric report")
    if metric_report.validation_plan_sha256 != canonical_sha256(plan):
        raise ValueError("metric report validation-plan digest does not match diagnosis")
    if metric_report.covered_validation_check_keys != expected_keys:
        raise ValueError(
            "metric report does not cover the exact deterministic validation checks"
        )
    curve_bundle_raw = inputs.get("curve_bundle")
    if curve_bundle_raw is None:
        if diagnosis.curve_analysis is not None:
            raise ValueError("curve analysis requires the exact curve_bundle input")
        return
    curve_bundle = CurveBundle.model_validate_json(curve_bundle_raw, strict=True)
    analyzable = failed_residual_analysis_available(portfolio, metric_report)
    if diagnosis.curve_analysis is None:
        if analyzable:
            raise ValueError(
                "failed residual metric with curve_bundle requires curve_analysis"
            )
        return
    expected_analysis = analyze_curve_error(
        portfolio,
        metric_report,
        curve_bundle,
        comparison_key=diagnosis.curve_analysis.selection_comparison_key,
    ).report
    if canonical_json(expected_analysis) != canonical_json(diagnosis.curve_analysis):
        raise ValueError("curve analysis does not reproduce from exact task inputs")


__all__ = [
    "GateStatus",
    "LayeredDiagnosisReport",
    "ObjectiveDiagnosisAssessment",
    "ScientificGateResult",
    "ScientificGateSequence",
    "validate_tcad_diagnosis_task_output",
    "validate_layered_diagnosis",
]
