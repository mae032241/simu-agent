"""Reviewable scientific facts with explicit applicability and provenance."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_objective import ResearchObjectiveContract


ScalarValue = str | int | float | bool
SourceType = Literal[
    "frozen_input",
    "web_snapshot",
    "user_statement",
    "runtime_output",
]
EpistemicStatus = Literal[
    "paper_fact",
    "user_defined",
    "runtime_observation",
    "inference",
    "assumption",
    "speculation",
]


class ApplicabilityCondition(SchemaModel):
    name: Identifier
    value: ScalarValue
    unit: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class EvidenceUncertainty(SchemaModel):
    description: Annotated[str, Field(min_length=1, max_length=2048)]
    value: int | float | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    basis: Annotated[str, Field(min_length=1, max_length=2048)]

    @model_validator(mode="after")
    def _numeric_value_has_unit(self) -> EvidenceUncertainty:
        if self.value is not None and self.unit is None:
            raise ValueError("numeric uncertainty requires a unit")
        return self


class FoundationEvidence(SchemaModel):
    source_key: Identifier
    source_type: SourceType
    title: Annotated[str, Field(min_length=1, max_length=2048)]
    locator: Annotated[str, Field(min_length=1, max_length=4096)]
    excerpt: Annotated[str, Field(min_length=1, max_length=2048)] | None = None


class EvidenceItem(SchemaModel):
    item_key: Identifier
    item_type: Literal[
        "fact",
        "parameter",
        "structure",
        "target_data",
        "constraint",
        "prior_observation",
        "assumption",
        "open_question",
    ]
    epistemic_status: EpistemicStatus
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    value: ScalarValue | None = None
    unit: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    scope: Annotated[str, Field(min_length=1, max_length=4096)]
    conditions: Annotated[
        tuple[ApplicabilityCondition, ...], Field(max_length=64)
    ] = ()
    uncertainty: EvidenceUncertainty | None = None
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)] | None = None
    tags: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _scientific_basis_is_explicit(self) -> EvidenceItem:
        if self.item_type == "parameter":
            if self.value is None:
                raise ValueError("parameter item requires a value")
            if self.unit is None:
                raise ValueError(
                    "parameter item requires a unit; use 'dimensionless' when applicable"
                )
        if self.value is None and self.unit is not None:
            raise ValueError("unit cannot be declared without a value")
        if self.epistemic_status in {
            "paper_fact",
            "user_defined",
            "runtime_observation",
        } and not self.evidence_keys:
            raise ValueError("source-backed evidence item requires evidence_keys")
        if self.epistemic_status in {
            "inference",
            "assumption",
            "speculation",
        } and self.rationale is None:
            raise ValueError("non-factual evidence item requires a rationale")
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise ValueError("evidence_keys must be unique")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("tags must be unique")
        condition_names = tuple(item.name for item in self.conditions)
        if len(condition_names) != len(set(condition_names)):
            raise ValueError("condition names must be unique within one evidence item")
        return self


class EvidenceConflict(SchemaModel):
    conflict_key: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    item_keys: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()
    status: Literal["unresolved", "resolved", "accepted_assumption"]
    resolution: Annotated[str, Field(min_length=1, max_length=4096)] | None = None

    @model_validator(mode="after")
    def _resolution_matches_status(self) -> EvidenceConflict:
        if self.status == "unresolved" and self.resolution is not None:
            raise ValueError("unresolved conflict cannot declare a resolution")
        if self.status != "unresolved" and self.resolution is None:
            raise ValueError("resolved conflict requires a resolution")
        if len(self.item_keys) != len(set(self.item_keys)):
            raise ValueError("conflict item_keys must be unique")
        return self


class ScientificFoundation(SchemaModel):
    """Human-reviewable scientific basis for downstream hypothesis work."""

    title: Annotated[str, Field(min_length=1, max_length=2048)]
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    summary: Annotated[str, Field(min_length=1, max_length=8192)]
    objective_contract: ResearchObjectiveContract | None = None
    items: Annotated[tuple[EvidenceItem, ...], Field(min_length=1, max_length=512)]
    evidence: Annotated[
        tuple[FoundationEvidence, ...], Field(max_length=512)
    ] = ()
    conflicts: Annotated[tuple[EvidenceConflict, ...], Field(max_length=128)] = ()
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=128)] = ()
    open_questions: Annotated[tuple[str, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _references_are_local_and_complete(self) -> ScientificFoundation:
        item_keys = tuple(item.item_key for item in self.items)
        source_keys = tuple(item.source_key for item in self.evidence)
        conflict_keys = tuple(item.conflict_key for item in self.conflicts)
        if len(item_keys) != len(set(item_keys)):
            raise ValueError("item_key values must be unique")
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("source_key values must be unique")
        if len(conflict_keys) != len(set(conflict_keys)):
            raise ValueError("conflict_key values must be unique")
        known_items = set(item_keys)
        known_sources = set(source_keys)
        for item in self.items:
            if not set(item.evidence_keys).issubset(known_sources):
                raise ValueError("evidence item references an undeclared source_key")
        for conflict in self.conflicts:
            if not set(conflict.item_keys).issubset(known_items):
                raise ValueError("conflict references an undeclared item_key")
        if self.objective_contract is not None:
            if self.objective_contract.statement != self.objective:
                raise ValueError(
                    "objective contract statement must equal the foundation objective"
                )
            for target in self.objective_contract.mandatory_targets:
                if not set(target.evidence_item_keys).issubset(known_items):
                    raise ValueError(
                        "objective target references an undeclared foundation item"
                    )
        return self


def validate_scientific_foundation(value: dict[str, object]) -> dict[str, object]:
    return ScientificFoundation.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "ApplicabilityCondition",
    "EvidenceConflict",
    "EvidenceItem",
    "EvidenceUncertainty",
    "FoundationEvidence",
    "ScientificFoundation",
    "validate_scientific_foundation",
]
