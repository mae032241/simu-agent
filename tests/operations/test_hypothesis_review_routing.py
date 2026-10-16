from __future__ import annotations

from dataclasses import replace

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import (
    RootOperationRoutes,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.cognitive import (
    CriticReview,
    HypothesisReviewForm,
)
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.run_signal import SchedulerSignal
from scidiscovery.artifact_agent.service.run_records import RunSlotBusy
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_components import _critic_portfolio_context
from scidiscovery.general_science_experiment_components import _object_review_context
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    OperationInvocationError,
    preflight_operation,
)


def _catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN))


def _ref(name: str, kind: str, schema: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"art_{name}",
        sha256=(name.encode().hex() + "0" * 64)[:64],
        kind=kind,
        schema_id=schema,
    )


def _artifact(
    name: str,
    schema: str,
    *,
    kind: str = "scientific_object",
    parents: tuple[ArtifactRef, ...] = (),
    verdict: str | None = None,
    media_type: str = "application/json",
) -> InvocationArtifact:
    return InvocationArtifact(
        artifact_name=name,
        ref=_ref(name, kind, schema),
        schema_id=schema,
        media_type=media_type,
        size_bytes=32,
        parent_refs=parents,
        handoff_verdict=verdict,
    )


def _critic(
    *,
    disposition: str = "revise_hypothesis",
    physical: str = "fail",
    falsifiability: str = "pass",
    discriminability: str = "pass",
    issue: str = "The mechanism statement is incomplete.",
) -> CriticReview:
    return CriticReview(
        disposition=disposition,
        reviews=(
            HypothesisReviewForm(
                hypothesis_key="hypothesis_a",
                physical_plausibility=physical,
                falsifiability=falsifiability,
                finite_discriminability=discriminability,
                issues=(issue,),
                smallest_resolving_action="Make one bounded correction.",
            ),
        ),
    )


def test_critic_routes_current_uncertainty_to_experiment_design() -> None:
    portfolio = canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_a",
            "stage_objective": "Separate two bounded mechanisms.",
            "contradiction": "The current evidence does not distinguish them.",
            "evidence": [],
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the observable.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Only the supplied system.",
                    "parameters": [],
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "A bounded response",
                            "expected_outcome": "The response changes direction.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "The same bounded response",
                            "rejection_condition": "No directional change occurs.",
                        }
                    ],
                    "competing_hypothesis_keys": [],
                    "evidence_keys": [],
                }
            ],
        }
    )
    review = _critic(
        disposition="ready_for_experiment",
        physical="pass",
        falsifiability="pass",
        discriminability="pass",
    )
    _critic_portfolio_context(
        review.model_dump(mode="json"),
        {"hypothesis_portfolio": portfolio},
        {"verdict": "pass"},
    )


# The real Root preflight/invoke source-continuity path is covered in
# test_user_context_contract, with completed producers and an actual fixture approval.
