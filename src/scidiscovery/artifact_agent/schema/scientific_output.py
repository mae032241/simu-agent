"""Minimal machine-readable envelope shared by cognitive scientific roles."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json


class EvidenceCitation(SchemaModel):
    source_key: Identifier
    source_type: Literal[
        "frozen_input",
        "web_snapshot",
        "user_statement",
        "runtime_output",
        "inference",
    ]
    locator: Annotated[str, Field(min_length=1, max_length=4096)]
    excerpt: Annotated[str, Field(min_length=1, max_length=1024)] | None = None


class ScientificFinding(SchemaModel):
    finding_key: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    epistemic_status: Literal[
        "paper_fact",
        "user_defined",
        "runtime_observation",
        "inference",
        "assumption",
        "speculation",
    ]
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)] | None = None


class ScientificRoleOutput(SchemaModel):
    """Stable evidence shell with an intentionally open role-specific payload."""

    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    findings: Annotated[tuple[ScientificFinding, ...], Field(max_length=256)] = ()
    evidence: Annotated[tuple[EvidenceCitation, ...], Field(max_length=256)] = ()
    assumptions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    open_questions: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    role_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _references_exist(self) -> ScientificRoleOutput:
        keys = tuple(item.source_key for item in self.evidence)
        if len(keys) != len(set(keys)):
            raise ValueError("evidence source_key values must be unique")
        known = set(keys)
        for finding in self.findings:
            if len(finding.evidence_keys) != len(set(finding.evidence_keys)):
                raise ValueError("finding evidence_keys must be unique")
            if not set(finding.evidence_keys).issubset(known):
                raise ValueError("finding references an undeclared evidence key")
            if finding.epistemic_status in {
                "paper_fact",
                "user_defined",
                "runtime_observation",
            } and not finding.evidence_keys:
                raise ValueError("source-backed finding requires evidence")
        return self


def validate_scientific_role_output(value: dict[str, object]) -> dict[str, object]:
    return ScientificRoleOutput.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "EvidenceCitation",
    "ScientificFinding",
    "ScientificRoleOutput",
    "validate_scientific_role_output",
]
