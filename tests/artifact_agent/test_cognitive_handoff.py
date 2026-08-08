from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.cognitive import (
    CriticReview,
    EvidenceAudit,
    HypothesisProposal,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.role_result import (
    RoleResultEnvelope,
    role_result_json_schema,
)
from scidiscovery.artifact_agent.transforms import _knowledge_portfolio_view
from scidiscovery.platforms.roles import load_roles, role_output_json_schema


def hypothesis_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "objective": "Reproduce the full Fig.4 zinc profile.",
        "contradiction": "The baseline front is shallower than the target.",
        "evidence": [
            {
                "source_key": "baseline_metrics",
                "source_type": "runtime_output",
                "locator": "full_curve.front_depth_nm",
            }
        ],
        "hypotheses": [
            {
                "hypothesis_key": "shared_diffusivity",
                "statement": "The shared Zn diffusivity is too low.",
                "mechanism": "A larger interstitial diffusivity advances the front.",
                "scope": "The frozen single-layer InGaAs experiment.",
                "parameters": [
                    {
                        "name": "Zinc.IntIII.D(+1)",
                        "role": "calibratable",
                        "unit": "cm2/s",
                        "range_description": "0.7x to 1.3x the frozen baseline",
                        "basis": "A symmetric bounded sensitivity test.",
                    }
                ],
                "predictions": [
                    {
                        "prediction_key": "front_moves",
                        "observable": "full zinc depth profile",
                        "expected_outcome": "Front depth changes monotonically.",
                    }
                ],
                "falsifiers": [
                    {
                        "falsifier_key": "shape_not_recovered",
                        "observable": "full-curve log RMSE",
                        "rejection_condition": "No bounded value improves the baseline.",
                    }
                ],
                "evidence_keys": ["baseline_metrics"],
            }
        ],
    }


def critic_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "reviews": [
            {
                "hypothesis_key": "shared_diffusivity",
                "physical_plausibility": "pass",
                "falsifiability": "pass",
                "identifiability": "pass",
            }
        ],
    }


def evidence_audit_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence": [
            {
                "source_key": "baseline_metrics",
                "source_type": "runtime_output",
                "locator": "full_curve",
            }
        ],
        "checks": [
            {
                "check_key": "baseline_residual",
                "subject": "The claimed baseline mismatch exists.",
                "status": "pass",
                "basis": "The frozen full-curve metric reports it.",
                "evidence_keys": ["baseline_metrics"],
            }
        ],
    }


def role_envelope(
    payload: dict[str, object],
    *,
    verdict: str = "pass",
    summary: str = "The role payload is complete.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "handoff": {"verdict": verdict, "summary": summary},
        "payload": payload,
    }


def test_every_worker_role_uses_one_result_envelope() -> None:
    for role in load_roles():
        schema = role_output_json_schema(role)
        assert schema["title"].startswith("RoleResultEnvelope[")
        assert set(schema["properties"]) == {"schema_version", "handoff", "payload"}
        assert set(schema["required"]) == {"schema_version", "handoff", "payload"}


def test_compact_payloads_validate_without_nested_schema_versions() -> None:
    portfolio = HypothesisProposal.model_validate_json(
        canonical_json(hypothesis_payload()), strict=True
    )
    critic = CriticReview.model_validate_json(
        canonical_json(critic_payload()), strict=True
    )
    audit = EvidenceAudit.model_validate_json(
        canonical_json(evidence_audit_payload()), strict=True
    )

    assert portfolio.hypotheses[0].hypothesis_key == "shared_diffusivity"
    assert critic.reviews[0].identifiability == "pass"
    assert audit.checks[0].status == "pass"
    assert "schema_version" not in portfolio.model_dump(mode="json")["hypotheses"][0]


def test_typed_envelope_validates_handoff_and_payload_together() -> None:
    model = RoleResultEnvelope[HypothesisProposal]
    result = model.model_validate_json(
        canonical_json(role_envelope(hypothesis_payload())), strict=True
    )

    assert result.handoff.verdict == "pass"
    assert result.payload.hypotheses[0].hypothesis_key == "shared_diffusivity"
    assert role_result_json_schema(HypothesisProposal)["properties"]["payload"]


def test_payload_rejects_unknown_evidence_reference() -> None:
    value = hypothesis_payload()
    value["hypotheses"][0]["evidence_keys"] = ["not_declared"]
    with pytest.raises(ValidationError, match="undeclared evidence"):
        HypothesisProposal.model_validate_json(canonical_json(value), strict=True)


def test_unresolved_critic_row_requires_one_resolving_action() -> None:
    value = critic_payload()
    value["reviews"][0]["identifiability"] = "unknown"
    with pytest.raises(ValidationError, match="smallest_resolving_action"):
        CriticReview.model_validate_json(canonical_json(value), strict=True)


def test_hypothesis_payload_builds_narrow_knowledge_view() -> None:
    portfolio = _knowledge_portfolio_view(canonical_json(hypothesis_payload()))

    assert portfolio.ranking == ("shared_diffusivity",)
    assert portfolio.hypotheses[0].status == "testable"
    assert portfolio.hypotheses[0].support_level == "unassessed"
    assert portfolio.hypotheses[0].predictions[0].prediction_key == "front_moves"
