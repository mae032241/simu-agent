from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.cognitive import HypothesisProposal
from scidiscovery.artifact_agent.schema.hypothesis import HypothesisPortfolio
from scidiscovery.artifact_agent.schema.knowledge import (
    KnowledgeUpdate,
    advance_knowledge_state,
    derive_knowledge_update,
    project_knowledge_state,
    validate_knowledge_update,
    validate_update_against_inputs,
)
from scidiscovery.artifact_agent.schema.validation import ValidationReport
from scidiscovery.artifact_agent.transforms import ScientificStateTransformAdapter


def _portfolio() -> HypothesisPortfolio:
    return HypothesisPortfolio.model_validate_json(
        canonical_json(
            {
                "objective": "Explain the measured response difference.",
                "contradiction": "The baseline misses the measured curve shape.",
                "foundation_summary": "The structure and target curve are frozen.",
                "foundation_item_keys": ["target_curve", "device_structure"],
                "hypotheses": [
                    {
                        "hypothesis_key": "field_localization",
                        "statement": "Lateral topology localizes the electric field.",
                        "mechanism": "A lateral junction edge creates a field maximum.",
                        "scope": "The frozen complete device at the measured temperature.",
                        "predictions": [
                            {
                                "prediction_key": "edge_field_peak",
                                "observable": "Electric-field map",
                                "expected_outcome": "A resolved edge field peak appears.",
                                "rationale": "This is the direct mechanism signature.",
                            }
                        ],
                        "falsifiers": [
                            {
                                "falsifier_key": "no_edge_peak",
                                "observable": "Electric-field map",
                                "rejection_condition": "No peak appears in a converged mesh study.",
                                "rationale": "The mechanism requires localization.",
                            }
                        ],
                        "status": "under_test",
                        "support_level": "low",
                        "support_rationale": "The mechanism has not yet passed its field test.",
                    }
                ],
                "ranking": ["field_localization"],
                "ranking_rationale": "This is the only selected mechanism.",
            }
        ),
        strict=True,
    )


def _proposal() -> HypothesisProposal:
    return HypothesisProposal.model_validate_json(
        canonical_json(
            {
                "schema_version": 1,
                "objective": "Explain the measured response difference.",
                "contradiction": "The baseline misses the measured curve shape.",
                "evidence": [
                    {
                        "source_key": "target_curve",
                        "source_type": "frozen_input",
                        "locator": "full measured curve",
                    }
                ],
                "hypotheses": [
                    {
                        "hypothesis_key": "field_localization",
                        "statement": "Lateral topology localizes the electric field.",
                        "mechanism": "A lateral junction edge creates a field maximum.",
                        "scope": "The frozen complete device at the measured temperature.",
                        "predictions": [
                            {
                                "prediction_key": "edge_field_peak",
                                "observable": "Electric-field map",
                                "expected_outcome": "A resolved edge field peak appears.",
                            }
                        ],
                        "falsifiers": [
                            {
                                "falsifier_key": "no_edge_peak",
                                "observable": "Electric-field map",
                                "rejection_condition": "No peak appears in a converged mesh study.",
                            }
                        ],
                        "evidence_keys": ["target_curve"],
                    }
                ],
            }
        ),
        strict=True,
    )


def _dimension(key: str, status: str) -> dict[str, object]:
    return {
        "status": status,
        "summary": f"{key} {status}.",
        "results": [
            {
                "check_key": key,
                "status": status,
                "evaluation_mode": "reviewed_qualitative",
                "observed_text": f"Observed {key} result.",
                "evidence_keys": ["run_output"],
                "rationale": "Compared with the pre-registered condition.",
            }
        ],
    }


def _report(*, numerical: str = "pass", physical: str = "fail") -> ValidationReport:
    overall = "fail" if "fail" in {numerical, physical} else "pass"
    return ValidationReport.model_validate_json(
        canonical_json(
            {
                "experiment_key": "field_study",
                "plan_key": "validate_field_study",
                "summary": "The run is numerically valid but the field prediction failed.",
                "evidence": [
                    {
                        "source_key": "run_output",
                        "source_type": "runtime_output",
                        "title": "Collected TCAD output",
                        "locator": "field.tdr",
                    }
                ],
                "numerical": _dimension("numerical_check", numerical),
                "physical": _dimension("physical_check", physical),
                "experimental": _dimension("experimental_check", "pass"),
                "overall_verdict": overall,
                "claim_allowed": overall == "pass",
                "next_action": "Update the tested hypothesis only.",
            }
        ),
        strict=True,
    )


def _update(*, outcome: str = "contradicts", new_status: str = "weakened") -> dict[str, object]:
    falsifiers = ["no_edge_peak"] if new_status == "rejected" else []
    return {
        "update_key": "field_study_update",
        "objective": "Update the tested field-localization hypothesis.",
        "hypothesis_portfolio_source_key": "hypothesis_portfolio",
        "validation_report_source_key": "validation_report",
        "experiment_key": "field_study",
        "validation_plan_key": "validate_field_study",
        "validation_verdict": "fail",
        "numerical_verdict": "pass",
        "evidence": [
            {
                "source_key": "hypothesis_portfolio",
                "source_type": "frozen_input",
                "title": "Frozen hypothesis portfolio",
                "locator": "field_localization",
            },
            {
                "source_key": "validation_report",
                "source_type": "runtime_output",
                "title": "Validated field study",
                "locator": "physical_check",
            },
        ],
        "transitions": [
            {
                "hypothesis_key": "field_localization",
                "prior_status": "under_test",
                "new_status": new_status,
                "prior_support_level": "low",
                "new_support_level": "low",
                "outcome": outcome,
                "evidence_keys": ["hypothesis_portfolio", "validation_report"],
                "predictions_checked": ["edge_field_peak"],
                "falsifiers_triggered": falsifiers,
                "rationale": "The valid field map does not show the required peak.",
            }
        ],
        "remaining_contradiction": "The measured curve shape remains unexplained.",
        "next_task_mode": "new_mechanism",
        "next_task_instruction": "Generate a competing mechanism using the frozen evidence.",
        "human_review_required": new_status == "rejected",
    }


def _parse_update(value: dict[str, object]) -> KnowledgeUpdate:
    return KnowledgeUpdate.model_validate_json(canonical_json(value), strict=True)


def test_valid_study_can_weaken_a_falsified_hypothesis() -> None:
    portfolio = _portfolio()
    report = _report()
    update = _parse_update(_update())
    validate_update_against_inputs(portfolio, report, update)
    projected = project_knowledge_state(portfolio, [update])
    assert projected.hypotheses[0].status == "weakened"
    assert projected.last_update_key == "field_study_update"
    assert validate_knowledge_update(_update())["schema_version"] == 1


def test_numerical_failure_cannot_be_used_as_physical_contradiction() -> None:
    value = _update()
    value["numerical_verdict"] = "fail"
    with pytest.raises(ValidationError, match="numerically valid failed prediction"):
        _parse_update(value)


def test_rejection_requires_falsifier_and_human_review() -> None:
    value = _update(new_status="rejected")
    value["transitions"][0]["falsifiers_triggered"] = []
    with pytest.raises(ValidationError, match="pre-registered falsifier"):
        _parse_update(value)
    value = _update(new_status="rejected")
    value["human_review_required"] = False
    with pytest.raises(ValidationError, match="human review"):
        _parse_update(value)


def test_projection_rejects_stale_prior_state() -> None:
    first = _parse_update(_update())
    second_value = _update()
    second_value["update_key"] = "second_update"
    second_value["previous_update_key"] = "field_study_update"
    second = _parse_update(second_value)
    with pytest.raises(ValueError, match="stale prior status"):
        project_knowledge_state(_portfolio(), [first, second])


def test_update_cross_check_rejects_report_mismatch() -> None:
    report = _report(numerical="fail")
    update = _parse_update(_update())
    with pytest.raises(ValueError, match="numerical verdict"):
        validate_update_against_inputs(_portfolio(), report, update)


def _report_requiring_update(
    *, outcome: str = "contradicts"
) -> ValidationReport:
    value = _report(physical="pass" if outcome == "supports" else "fail").model_dump(
        mode="json"
    )
    value["knowledge_update_applicability"] = "required"
    value["hypothesis_assessments"] = [
        {
            "hypothesis_key": "field_localization",
            "outcome": outcome,
            "evidence_keys": ["run_output"],
            "predictions_checked": ["edge_field_peak"],
            "rationale": "The valid field map does not show the required peak.",
        }
    ]
    value["remaining_contradiction"] = "The measured curve shape remains unexplained."
    value["recommended_task_mode"] = "new_mechanism"
    return ValidationReport.model_validate_json(canonical_json(value), strict=True)


def test_diagnosis_is_deterministically_converted_to_knowledge_update() -> None:
    update = derive_knowledge_update(_portfolio(), _report_requiring_update())
    assert update.transitions[0].new_status == "weakened"
    assert update.transitions[0].new_support_level == "low"
    assert update.human_review_required is False


def test_deterministic_update_continues_from_projected_state() -> None:
    portfolio = _portfolio()
    first = derive_knowledge_update(portfolio, _report_requiring_update())
    first_state = advance_knowledge_state(
        project_knowledge_state(portfolio, ()), first
    )
    second = derive_knowledge_update(
        portfolio,
        _report_requiring_update(outcome="supports"),
        prior_state=first_state,
    )
    assert second.previous_update_key == first.update_key
    assert second.transitions[0].prior_status == "weakened"
    assert second.transitions[0].new_status == "supported"
    assert second.transitions[0].new_support_level == "medium"
    second_state = advance_knowledge_state(first_state, second)
    assert second_state.last_update_key == second.update_key


def test_control_transform_creates_update_without_extra_agent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
            transform_adapters=(ScientificStateTransformAdapter(),),
        )
    )
    (project / "portfolio.json").write_bytes(_proposal().canonical_json())
    (project / "report.json").write_bytes(_report_requiring_update().canonical_json())
    portfolio = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "control.portfolio.rev1",
            "relative_path": "portfolio.json",
            "media_type": "application/json",
        },
    )
    report = root.call_tool(
        "artifact_ingest_file",
        {
            "name": "control.validation.rev1",
            "relative_path": "report.json",
            "media_type": "application/json",
        },
    )
    result = root.call_tool(
        "artifact_transform",
        {
            "name": "hypothesis_update",
            "profile": "scidiscovery.knowledge-update-from-validation.v1",
            "inputs": [
                {
                    "source_name": "hypothesis_portfolio",
                    "artifact_name": portfolio["name"],
                },
                {
                    "source_name": "validation_report",
                    "artifact_name": report["name"],
                },
            ],
        },
    )
    assert result["outputs"][0]["artifact_name"] == "hypothesis_update"
    assert result["outputs"][0]["schema"] == "scidiscovery.knowledge-update.v1"
    assert result["outputs"][1]["artifact_name"] == "hypothesis_update.state"
    assert result["outputs"][1]["schema"] == (
        "scidiscovery.knowledge-state-projection.v1"
    )
