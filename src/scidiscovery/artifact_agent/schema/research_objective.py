"""Domain-neutral research objective declarations."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .common import Identifier, SchemaModel


ObjectiveIntent = Literal[
    "external_reproduction",
    "mechanism_discrimination",
    "numerical_qualification",
    "engineering",
]
ComparisonPurpose = Literal[
    "target_fit",
    "numerical_convergence",
    "mechanism_separation",
    "implementation_sanity",
    "exploratory_diagnostic",
    "unspecified_legacy",
]


class ObjectiveTarget(SchemaModel):
    target_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    support_requirement: Literal["complete_observation", "qualified_subset"]
    evidence_item_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=64)
    ]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class ObjectiveClosureRequirement(SchemaModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "anyOf": [
                            {"not": {"required": ["requirement_type"]}},
                            {
                                "properties": {
                                    "requirement_type": {
                                        "const": "target_coverage"
                                    }
                                },
                                "required": ["requirement_type"],
                            },
                        ]
                    },
                    "then": {
                        "properties": {
                            "target_keys": {"minItems": 1},
                            "comparison_purposes": {"maxItems": 0},
                            "validation_check_keys": {"maxItems": 0},
                        },
                        "required": ["target_keys"],
                    },
                },
                {
                    "if": {
                        "properties": {
                            "requirement_type": {"const": "comparison_present"}
                        },
                        "required": ["requirement_type"],
                    },
                    "then": {
                        "properties": {
                            "comparison_purposes": {"minItems": 1},
                            "validation_check_keys": {"maxItems": 0},
                        },
                        "required": ["comparison_purposes"],
                    },
                },
                {
                    "if": {
                        "properties": {
                            "requirement_type": {
                                "const": "validation_check_present"
                            }
                        },
                        "required": ["requirement_type"],
                    },
                    "then": {
                        "properties": {
                            "target_keys": {"maxItems": 0},
                            "comparison_purposes": {"maxItems": 0},
                            "validation_check_keys": {"minItems": 1},
                        },
                        "required": ["validation_check_keys"],
                    },
                },
            ]
        }
    )

    requirement_key: Identifier
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    requirement_type: Literal[
        "target_coverage", "comparison_present", "validation_check_present"
    ] = "target_coverage"
    target_keys: Annotated[
        tuple[Identifier, ...],
        Field(max_length=64),
    ] = ()
    comparison_purposes: Annotated[
        tuple[ComparisonPurpose, ...],
        Field(max_length=16),
    ] = ()
    validation_check_keys: Annotated[
        tuple[Identifier, ...],
        Field(max_length=128),
    ] = ()

    @model_validator(mode="after")
    def _subjects_match_type(self) -> ObjectiveClosureRequirement:
        if self.requirement_type == "target_coverage":
            if not self.target_keys:
                raise ValueError("target_coverage requires target_keys")
            if self.comparison_purposes or self.validation_check_keys:
                raise ValueError("target_coverage accepts only target_keys")
        elif self.requirement_type == "comparison_present":
            if not self.comparison_purposes:
                raise ValueError("comparison_present requires comparison_purposes")
            if self.validation_check_keys:
                raise ValueError(
                    "comparison_present cannot declare validation_check_keys"
                )
        else:
            if not self.validation_check_keys:
                raise ValueError(
                    "validation_check_present requires validation_check_keys"
                )
            if self.target_keys or self.comparison_purposes:
                raise ValueError(
                    "validation_check_present accepts only validation_check_keys"
                )
        return self


class ResearchObjectiveContract(SchemaModel):
    objective_key: Identifier
    intent: ObjectiveIntent
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    mandatory_targets: Annotated[
        tuple[ObjectiveTarget, ...], Field(max_length=128)
    ] = ()
    closure_requirements: Annotated[
        tuple[ObjectiveClosureRequirement, ...], Field(min_length=1, max_length=128)
    ]

    @model_validator(mode="after")
    def _objective_is_complete(self) -> ResearchObjectiveContract:
        target_keys = tuple(item.target_key for item in self.mandatory_targets)
        requirement_keys = tuple(
            item.requirement_key for item in self.closure_requirements
        )
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("objective target keys must be unique")
        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError("objective closure requirement keys must be unique")
        if self.intent == "external_reproduction" and not self.mandatory_targets:
            raise ValueError(
                "external-reproduction objective requires a mandatory external target"
            )
        known_targets = set(target_keys)
        for requirement in self.closure_requirements:
            if not set(requirement.target_keys).issubset(known_targets):
                raise ValueError("closure requirement references an unknown target")
        return self


__all__ = [
    "ComparisonPurpose",
    "ObjectiveClosureRequirement",
    "ObjectiveIntent",
    "ObjectiveTarget",
    "ResearchObjectiveContract",
]
