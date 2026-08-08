from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.transforms import (
    CANDIDATE_ELIGIBILITY_PROFILE,
    ScientificStateTransformAdapter,
)
from tests.artifact_agent.test_cognitive_handoff import (
    critic_payload,
    evidence_audit_payload,
    hypothesis_payload,
)


def _transform(
    portfolio: dict[str, object],
    critic: dict[str, object],
    audit: dict[str, object],
) -> dict[str, object]:
    output = ScientificStateTransformAdapter.transform(
        profile=CANDIDATE_ELIGIBILITY_PROFILE,
        inputs={
            "hypothesis_portfolio": canonical_json(portfolio),
            "critic_review": canonical_json(critic),
            "evidence_audit": canonical_json(audit),
        },
    )
    assert len(output) == 1
    assert output[0].kind == "candidate_eligibility"
    return json.loads(output[0].content)


def test_candidate_join_accepts_reviewed_compact_payloads() -> None:
    result = _transform(
        hypothesis_payload(), critic_payload(), evidence_audit_payload()
    )

    assert result["status"] == "ready"
    assert result["eligible_hypothesis_keys"] == ["shared_diffusivity"]


def test_unresolved_evidence_prevents_experiment_design_readiness() -> None:
    audit = deepcopy(evidence_audit_payload())
    audit["checks"][0]["status"] = "unknown"
    audit["checks"][0]["basis"] = "Target provenance remains unresolved."

    result = _transform(hypothesis_payload(), critic_payload(), audit)

    assert result["status"] == "revise"
    assert result["eligible_hypothesis_keys"] == []
    assert result["unresolved_requirements"] == [
        "Target provenance remains unresolved."
    ]


def test_candidate_join_rejects_incomplete_critic_coverage() -> None:
    critic = critic_payload()
    critic["reviews"] = []
    with pytest.raises(ValueError, match="cover every portfolio hypothesis"):
        _transform(hypothesis_payload(), critic, evidence_audit_payload())
