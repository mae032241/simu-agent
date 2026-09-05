from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml"


def test_current_architecture_constraint_matrix_has_stable_review_fields() -> None:
    """Check registry structure; semantic conformance requires independent review."""
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    constraints = payload["constraints"]
    identifiers = tuple(item["id"] for item in constraints)

    assert payload["schema_version"] == 1
    assert len(identifiers) == 33
    assert len(set(identifiers)) == 33
    assert identifiers == (
        "AUTH-001", "AUTH-002", "AUTH-003",
        "IMM-001", "IMM-002",
        "LIN-001", "LIN-002",
        "EVD-001", "EVD-002",
        "UNC-001", "UNC-002",
        "TOP-001", "TOP-002",
        "ROLE-001", "ROLE-002",
        "DET-001", "DET-002",
        "HIL-001", "HIL-002",
        "CQRS-001", "CQRS-002",
        "EFF-001", "EFF-002",
        "PLG-001", "PLG-002",
        "SEC-001", "SEC-002",
        "RES-001", "RES-002",
        "UI-001", "UI-002",
        "MIG-001", "MIG-002",
    )
    allowed_states = set(payload["assessment_states"])
    for item in constraints:
        assert item["assessment"] in allowed_states
        assert item["title"].strip()
        assert item["requirement"].strip()
        assert item["prohibited"].strip()
        assert item["evidence"].strip()
