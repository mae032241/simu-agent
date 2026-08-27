"""Falsifiable hypothesis portfolios grounded in a scientific foundation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Identifier, SchemaModel, canonical_json
from .scientific_foundation import ApplicabilityCondition


HypothesisStatus = Literal[
    "proposed",
    "testable",
    "under_test",
    "supported",
    "weakened",
    "rejected",
    "inconclusive",
]
SupportLevel = Literal["unassessed", "low", "medium", "high"]


class HypothesisParameter(SchemaModel):
    name: Identifier
    role: Literal["fixed", "calibratable", "missing"]
    unit: Annotated[str, Field(min_length=1, max_length=128)]
    range_description: Annotated[str, Field(min_length=1, max_length=2048)] | None = None
    basis: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _calibratable_parameter_is_bounded(self) -> HypothesisParameter:
        if self.role == "calibratable" and self.range_description is None:
            raise ValueError("calibratable parameter requires range_description")
        return self


class HypothesisPrediction(SchemaModel):
    prediction_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    expected_outcome: Annotated[str, Field(min_length=1, max_length=4096)]
    conditions: Annotated[
        tuple[ApplicabilityCondition, ...], Field(max_length=64)
    ] = ()
    distinguishes_from: Annotated[tuple[Identifier, ...], Field(max_length=32)] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class HypothesisFalsifier(SchemaModel):
    falsifier_key: Identifier
    observable: Annotated[str, Field(min_length=1, max_length=4096)]
    rejection_condition: Annotated[str, Field(min_length=1, max_length=4096)]
    conditions: Annotated[
        tuple[ApplicabilityCondition, ...], Field(max_length=64)
    ] = ()
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class EvidenceImpact(SchemaModel):
    item_key: Identifier
    direction: Literal["supports", "contradicts", "neutral"]
    strength: Literal["weak", "moderate", "strong"]
    rationale: Annotated[str, Field(min_length=1, max_length=4096)]


class HypothesisState(SchemaModel):
    hypothesis_key: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=8192)]
    mechanism: Annotated[str, Field(min_length=1, max_length=8192)]
    scope: Annotated[str, Field(min_length=1, max_length=4096)]
    prerequisites: Annotated[tuple[str, ...], Field(max_length=64)] = ()
    parameters: Annotated[tuple[HypothesisParameter, ...], Field(max_length=64)] = ()
    predictions: Annotated[
        tuple[HypothesisPrediction, ...], Field(min_length=1, max_length=64)
    ]
    falsifiers: Annotated[
        tuple[HypothesisFalsifier, ...], Field(min_length=1, max_length=64)
    ]
    competing_hypothesis_keys: Annotated[
        tuple[Identifier, ...], Field(max_length=32)
    ] = ()
    evidence_impacts: Annotated[
        tuple[EvidenceImpact, ...], Field(max_length=128)
    ] = ()
    status: HypothesisStatus
    support_level: SupportLevel
    support_rationale: Annotated[str, Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _keys_and_status_are_coherent(self) -> HypothesisState:
        for values, label in (
            (tuple(item.name for item in self.parameters), "parameter names"),
            (
                tuple(item.prediction_key for item in self.predictions),
                "prediction_key values",
            ),
            (
                tuple(item.falsifier_key for item in self.falsifiers),
                "falsifier_key values",
            ),
            (self.competing_hypothesis_keys, "competing_hypothesis_keys"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique")
        if self.status in {"supported", "weakened", "rejected"} and not self.evidence_impacts:
            raise ValueError("evidence-changing status requires evidence_impacts")
        if self.status == "supported" and self.support_level == "unassessed":
            raise ValueError("supported hypothesis cannot have unassessed support")
        return self


class HypothesisPortfolio(SchemaModel):
    objective: Annotated[str, Field(min_length=1, max_length=8192)]
    contradiction: Annotated[str, Field(min_length=1, max_length=8192)]
    foundation_summary: Annotated[str, Field(min_length=1, max_length=8192)]
    foundation_item_keys: Annotated[
        tuple[Identifier, ...], Field(min_length=1, max_length=512)
    ]
    hypotheses: Annotated[
        tuple[HypothesisState, ...], Field(min_length=1, max_length=12)
    ]
    ranking: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=12)]
    ranking_rationale: Annotated[str, Field(min_length=1, max_length=8192)]
    missing_inputs: Annotated[tuple[str, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _portfolio_is_closed(self) -> HypothesisPortfolio:
        hypothesis_keys = tuple(item.hypothesis_key for item in self.hypotheses)
        if len(hypothesis_keys) != len(set(hypothesis_keys)):
            raise ValueError("hypothesis_key values must be unique")
        if len(self.foundation_item_keys) != len(set(self.foundation_item_keys)):
            raise ValueError("foundation_item_keys must be unique")
        if len(self.ranking) != len(set(self.ranking)):
            raise ValueError("ranking must not contain duplicates")
        if set(self.ranking) != set(hypothesis_keys):
            raise ValueError("ranking must contain every hypothesis exactly once")
        known_hypotheses = set(hypothesis_keys)
        known_items = set(self.foundation_item_keys)
        for hypothesis in self.hypotheses:
            competitors = set(hypothesis.competing_hypothesis_keys)
            if hypothesis.hypothesis_key in competitors:
                raise ValueError("hypothesis cannot compete with itself")
            if not competitors.issubset(known_hypotheses):
                raise ValueError("hypothesis references an undeclared competitor")
            if not {impact.item_key for impact in hypothesis.evidence_impacts}.issubset(
                known_items
            ):
                raise ValueError("hypothesis references an undeclared foundation item")
            for prediction in hypothesis.predictions:
                if not set(prediction.distinguishes_from).issubset(known_hypotheses):
                    raise ValueError("prediction references an undeclared competitor")
                if hypothesis.hypothesis_key in prediction.distinguishes_from:
                    raise ValueError("prediction cannot distinguish a hypothesis from itself")
        return self


def validate_hypothesis_portfolio(value: dict[str, object]) -> dict[str, object]:
    return HypothesisPortfolio.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "EvidenceImpact",
    "HypothesisFalsifier",
    "HypothesisParameter",
    "HypothesisPortfolio",
    "HypothesisPrediction",
    "HypothesisState",
    "HypothesisStatus",
    "SupportLevel",
    "validate_hypothesis_portfolio",
]
