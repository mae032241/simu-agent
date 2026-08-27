"""Compact machine-readable decision shared by bounded review roles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_output import EvidenceCitation, ScientificFinding


class DecisionConstraint(SchemaModel):
    constraint_key: Identifier
    requirement: Annotated[str, Field(min_length=1, max_length=2048)]
    status: Literal["pass", "fail", "unknown", "not_applicable"]
    rationale: Annotated[str, Field(min_length=1, max_length=2048)]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=16)] = ()


class DecisionPacket(SchemaModel):
    """Small review result; detailed source content remains in parent artifacts."""

    verdict: Literal[
        "pass", "revise", "reject", "blocked", "inconclusive", "fail"
    ]
    summary: Annotated[str, Field(min_length=1, max_length=2048)]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]
    findings: Annotated[tuple[ScientificFinding, ...], Field(max_length=32)] = ()
    constraints: Annotated[tuple[DecisionConstraint, ...], Field(max_length=32)] = ()
    evidence: Annotated[tuple[EvidenceCitation, ...], Field(max_length=64)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    next_actions: Annotated[tuple[str, ...], Field(max_length=16)] = ()

    @model_validator(mode="after")
    def _references_exist(self) -> DecisionPacket:
        keys = tuple(item.source_key for item in self.evidence)
        if len(keys) != len(set(keys)):
            raise ValueError("evidence source_key values must be unique")
        known = set(keys)
        for finding in self.findings:
            if not set(finding.evidence_keys).issubset(known):
                raise ValueError("finding references an undeclared evidence key")
        for constraint in self.constraints:
            if not set(constraint.evidence_keys).issubset(known):
                raise ValueError("constraint references an undeclared evidence key")
        return self


def validate_decision_packet(value: dict[str, object]) -> dict[str, object]:
    return DecisionPacket.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = ["DecisionConstraint", "DecisionPacket", "validate_decision_packet"]
