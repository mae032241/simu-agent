"""Domain-neutral deterministic scientific transformations."""

from __future__ import annotations

from typing import Mapping

from .schema.experiment_intent import materialize_experiment_design_inputs
from .schema.scientific_foundation import ScientificFoundation


def project_research_objective(raw: bytes) -> bytes:
    foundation = ScientificFoundation.model_validate_json(raw, strict=True)
    if foundation.objective_contract is None:
        raise ValueError(
            "research objective projection requires an explicit objective_contract"
        )
    return foundation.objective_contract.canonical_json()


def materialize_experiment_plan(
    inputs: Mapping[str, bytes],
) -> tuple[bytes, bytes]:
    portfolio, report = materialize_experiment_design_inputs(dict(inputs))
    return portfolio.canonical_json(), report.canonical_json()


__all__ = [
    "materialize_experiment_plan",
    "project_research_objective",
]
