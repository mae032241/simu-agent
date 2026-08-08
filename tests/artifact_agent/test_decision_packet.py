from __future__ import annotations

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.decision import DecisionPacket


def test_decision_packet_keeps_bounded_review_fields() -> None:
    packet = DecisionPacket.model_validate(
        {
            "verdict": "revise",
            "summary": "One execution gate is incomplete.",
            "rationale": "The candidate is testable after the scorer is frozen.",
            "evidence": (
                {
                    "source_key": "candidate_review",
                    "source_type": "frozen_input",
                    "locator": "constraint table",
                },
            ),
            "constraints": (
                {
                    "constraint_key": "scorer_frozen",
                    "requirement": "Freeze the deterministic scorer before execution.",
                    "status": "fail",
                    "rationale": "The scorer version is absent.",
                    "evidence_keys": ("candidate_review",),
                },
            ),
            "missing_inputs": ("scorer version",),
            "next_actions": ("freeze scorer",),
        }
    )
    assert packet.verdict == "revise"
    assert packet.constraints[0].status == "fail"
    assert "role_payload" not in packet.model_dump(mode="json")


def test_decision_packet_rejects_unknown_evidence_reference() -> None:
    with pytest.raises(ValidationError, match="undeclared evidence"):
        DecisionPacket.model_validate(
            {
                "verdict": "reject",
                "summary": "Unsupported claim.",
                "rationale": "The required source is absent.",
                "constraints": (
                    {
                        "constraint_key": "source_present",
                        "requirement": "Supply a source.",
                        "status": "fail",
                        "rationale": "No source is supplied.",
                        "evidence_keys": ("missing_source",),
                    },
                ),
            }
        )
