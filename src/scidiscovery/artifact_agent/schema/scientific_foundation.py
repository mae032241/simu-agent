"""Reviewable scientific facts with explicit applicability and provenance."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .research_objective import ResearchObjectiveContract


# These declarations are also the Worker-visible field contract. Unknown values
# remain None; absence of a measurement must never force an invented number.
PARAMETER_UNIT_RULE = "A parameter with a known value requires a unit; use 'dimensionless' when applicable. Unknown parameters may omit value and unit and explain the gap in statement."
VALUE_UNIT_RULE = "A unit cannot be declared without a value."
SOURCE_RULE = "Paper facts, user definitions and runtime observations require evidence_keys naming exact supplied sources."
RATIONALE_RULE = "Inference, assumption and speculation require rationale explaining the reasoning beyond the statement."
UNCERTAINTY_RULE = "Numeric uncertainty requires a unit."
IDENTITY_RULE = "Condition names must be unique within one evidence item."
FOUNDATION_RULES = (PARAMETER_UNIT_RULE, VALUE_UNIT_RULE, SOURCE_RULE, RATIONALE_RULE,
    UNCERTAINTY_RULE, IDENTITY_RULE,
    "Item and conflict keys must be unique. Conflicts reference only declared item keys.",
    "Unresolved conflicts have no resolution; resolved and accepted-assumption conflicts require resolution.",
    "A supplied objective contract statement equals the foundation objective and its targets reference declared items.")


def _raise_issues(model, issues):
    if issues:
        from ...operation_contract import declared_violation
        raise ValidationError.from_exception_data(type(model).__name__, [
            {"type": "value_error", "loc": path, "input": None,
             "ctx": {"error": declared_violation(message)}} for path, message in issues])


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
    unit: Annotated[str, Field(min_length=1, max_length=128, description=UNCERTAINTY_RULE)] | None = None
    basis: Annotated[str, Field(min_length=1, max_length=2048)]

    @model_validator(mode="after")
    def _numeric_value_has_unit(self) -> EvidenceUncertainty:
        if self.value is not None and self.unit is None:
            _raise_issues(self, [(("unit",), UNCERTAINTY_RULE)])
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
    value: ScalarValue | None = Field(default=None, description=PARAMETER_UNIT_RULE)
    unit: Annotated[str, Field(min_length=1, max_length=128, description=VALUE_UNIT_RULE + " " + PARAMETER_UNIT_RULE)] | None = None
    scope: Annotated[str, Field(min_length=1, max_length=4096)]
    conditions: Annotated[
        tuple[ApplicabilityCondition, ...], Field(max_length=64)
    ] = ()
    uncertainty: EvidenceUncertainty | None = None
    evidence_keys: Annotated[tuple[Identifier, ...], Field(max_length=64, description=SOURCE_RULE)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096, description=RATIONALE_RULE)] | None = None
    tags: Annotated[tuple[Identifier, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def _scientific_basis_is_explicit(self) -> EvidenceItem:
        issues = []
        if self.item_type == "parameter" and self.value is not None and self.unit is None:
            issues.append((("unit",), PARAMETER_UNIT_RULE))
        if self.value is None and self.unit is not None:
            issues.append((("unit",), VALUE_UNIT_RULE))
        if self.epistemic_status in {"paper_fact", "user_defined", "runtime_observation"} and not self.evidence_keys:
            issues.append((("evidence_keys",), SOURCE_RULE))
        if self.epistemic_status in {"inference", "assumption", "speculation"} and self.rationale is None:
            issues.append((("rationale",), RATIONALE_RULE))
        condition_names = tuple(item.name for item in self.conditions)
        if len(condition_names) != len(set(condition_names)):
            issues.append((("conditions",), IDENTITY_RULE))
        _raise_issues(self, issues)
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
        issues = []
        item_keys = tuple(item.item_key for item in self.items)
        conflict_keys = tuple(item.conflict_key for item in self.conflicts)
        if len(item_keys) != len(set(item_keys)):
            issues.append((("items",), "item_key values must be unique"))
        if len(conflict_keys) != len(set(conflict_keys)):
            issues.append((("conflicts",), "conflict_key values must be unique"))
        known_items = set(item_keys)
        for index, conflict in enumerate(self.conflicts):
            if not set(conflict.item_keys).issubset(known_items):
                issues.append((("conflicts", index, "item_keys"), "conflict references an undeclared item_key"))
        if self.objective_contract is not None:
            if self.objective_contract.statement != self.objective:
                issues.append((("objective",), "objective contract statement must equal the foundation objective"))
            for index, target in enumerate(self.objective_contract.mandatory_targets):
                if not set(target.evidence_item_keys).issubset(known_items):
                    issues.append((("objective_contract", "mandatory_targets", index, "evidence_item_keys"), "objective target references an undeclared foundation item"))
        _raise_issues(self, issues)
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
