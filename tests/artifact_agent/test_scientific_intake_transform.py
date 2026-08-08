from __future__ import annotations

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.transforms import (
    SCIENTIFIC_INTAKE_SPLIT_PROFILE,
    ScientificStateTransformAdapter,
)


def test_scientific_intake_is_deterministically_split() -> None:
    foundation = {
        "title": "Minimal foundation",
        "objective": "Reproduce one target curve.",
        "summary": "One target is frozen.",
        "evidence": [
            {
                "source_key": "paper",
                "source_type": "frozen_input",
                "title": "Paper",
                "locator": "paper.pdf#fig4",
            }
        ],
        "items": [
            {
                "item_key": "target",
                "item_type": "target_data",
                "epistemic_status": "paper_fact",
                "statement": "The target is Fig.4.",
                "scope": "Fig.4 only.",
                "evidence_keys": ["paper"],
            }
        ],
    }
    frame = {
        "title": "Minimal frame",
        "scientific_question": "Can the curve be reproduced?",
        "objective": "Reproduce one target curve.",
        "current_contradiction": "The baseline misses the target.",
        "scope": "Fig.4 only.",
        "foundation_item_keys": ["target"],
        "observables": [
            {
                "observable_key": "profile",
                "description": "Concentration versus depth.",
                "role": "target",
                "foundation_item_keys": ["target"],
                "acceptance_relevance": "It is the target curve.",
            }
        ],
        "claim_boundary": {
            "allowed_claim": "The scoped curve is reproduced.",
            "required_conditions": ["All scientific gates pass."],
        },
        "stop_conditions": ["The target metric passes."],
    }
    outputs = ScientificStateTransformAdapter.transform(
        profile=SCIENTIFIC_INTAKE_SPLIT_PROFILE,
        inputs={"scientific_intake": canonical_json({
            "problem_frame": frame,
            "scientific_foundation": foundation,
        })},
    )
    assert [item.label for item in outputs] == [
        "primary",
        "scientific_foundation",
    ]
    assert outputs[0].schema == "scidiscovery.problem-frame.v1"
