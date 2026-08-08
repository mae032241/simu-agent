from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_worker import WorkerMCPRouter
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.scientific_foundation import (
    ScientificFoundation,
    validate_scientific_foundation,
)
from scidiscovery.artifact_agent.schema.common import canonical_json


def _valid_foundation() -> dict[str, object]:
    return {
        "title": "Fig. 4 single-layer Zn diffusion foundation",
        "objective": "Reproduce the 480 C, 8 min total-Zn profile.",
        "summary": "The paper supplies one coefficient set and a target profile.",
        "evidence": [
            {
                "source_key": "paper",
                "source_type": "frozen_input",
                "title": "Zn diffusion paper",
                "locator": "Table I and Fig. 4",
                "excerpt": "DA=1.05e-12 cm2/s at 480 C",
            }
        ],
        "items": [
            {
                "item_key": "da_ingaas_480c",
                "item_type": "parameter",
                "epistemic_status": "paper_fact",
                "statement": "The reported Model-A diffusion coefficient is 1.05e-12 cm2/s.",
                "value": 1.05e-12,
                "unit": "cm^2/s",
                "scope": "Single-layer InGaAs Zn diffusion in the paper's Table I model.",
                "conditions": [
                    {"name": "temperature", "value": 480, "unit": "degC"},
                    {"name": "duration", "value": 8, "unit": "min"},
                ],
                "uncertainty": {
                    "description": "No coefficient uncertainty is reported.",
                    "basis": "The paper gives a point estimate only.",
                },
                "evidence_keys": ["paper"],
                "tags": ["zinc", "diffusion"],
            },
            {
                "item_key": "surface_reservoir",
                "item_type": "assumption",
                "epistemic_status": "assumption",
                "statement": "The source boundary is represented by a finite reservoir.",
                "scope": "Numerical realization of the Fig. 4 replay only.",
                "rationale": "The paper does not fully specify the source boundary condition.",
            },
        ],
        "conflicts": [
            {
                "conflict_key": "source_boundary_missing",
                "statement": "The source boundary realization is not reported by the paper.",
                "item_keys": ["surface_reservoir"],
                "status": "accepted_assumption",
                "resolution": "Retain as a declared numerical assumption and test sensitivity.",
            }
        ],
        "missing_inputs": ["Independent uncertainty for Table I coefficients."],
        "open_questions": ["Does the source-boundary choice alter the fitted front width?"],
    }


def _valid_intake() -> dict[str, object]:
    foundation = _valid_foundation()
    return {
        "problem_frame": {
            "title": "Fig. 4 single-layer Zn diffusion",
            "scientific_question": "Can the declared model reproduce the profile?",
            "objective": foundation["objective"],
            "current_contradiction": "The current baseline misses the target front.",
            "scope": "The paper's single-layer Fig. 4 experiment.",
            "foundation_item_keys": ["da_ingaas_480c", "surface_reservoir"],
            "observables": [
                {
                    "observable_key": "zinc_depth_profile",
                    "description": "Zinc concentration as a function of depth.",
                    "role": "target",
                    "foundation_item_keys": ["da_ingaas_480c"],
                    "acceptance_relevance": "The full curve determines reproduction quality.",
                }
            ],
            "claim_boundary": {
                "allowed_claim": "The model reproduces the scoped profile.",
                "required_conditions": ["All pre-registered gates pass."],
            },
            "stop_conditions": ["The full-curve threshold passes."],
        },
        "scientific_foundation": foundation,
    }


def test_foundation_accepts_explicit_scope_conditions_and_provenance() -> None:
    foundation = ScientificFoundation.model_validate_json(
        canonical_json(_valid_foundation()), strict=True
    )
    assert foundation.items[0].conditions[0].value == 480
    assert foundation.items[1].rationale is not None
    assert validate_scientific_foundation(_valid_foundation())["schema_version"] == 1


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["items"][0].pop("unit"),
            "parameter item requires a unit",
        ),
        (
            lambda value: value["items"][0].update(evidence_keys=[]),
            "source-backed evidence item requires evidence_keys",
        ),
        (
            lambda value: value["items"][1].pop("rationale"),
            "non-factual evidence item requires a rationale",
        ),
        (
            lambda value: value["items"][0].update(evidence_keys=["missing"]),
            "undeclared source_key",
        ),
    ],
)
def test_foundation_rejects_incomplete_scientific_basis(mutation, message) -> None:
    value = _valid_foundation()
    mutation(value)
    with pytest.raises(ValidationError, match=message):
        ScientificFoundation.model_validate_json(canonical_json(value), strict=True)


def test_evidence_extractor_assignment_uses_specialized_schema(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "paper.txt").write_text("Table I", encoding="utf-8")
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance="test",
        )
    )
    paper = root.call_tool(
        "artifact_ingest_file",
        {"name": "paper_pdf", "relative_path": "paper.txt", "media_type": "text/plain"},
    )
    task_name = root.call_tool(
        "task_schedule",
        {
            "name": "paper_foundation",
            "role": "evidence_extractor",
            "instruction": "Build one foundation.",
            "inputs": [
                {"source_name": "paper", "artifact_name": paper["name"]},
            ],
        },
    )["name"]
    root.call_tool("task_prepare_dispatch", {"name": task_name, "ttl_seconds": 60})
    worker = WorkerMCPRouter(runtime.tasks, worker_id="evidence_extractor")
    worker.call_tool("worker_claim_task", {})
    assignment = worker.call_tool("worker_get_assignment", {})
    assert assignment["output"]["json_schema"]["title"] == (
        "RoleResultEnvelope[ScientificIntake]"
    )
    assert "scope" in str(assignment["output"]["json_schema"])
    valid = _valid_intake()
    result = {
        "schema_version": 1,
        "handoff": {
            "verdict": "pass",
            "summary": "Foundation is ready for human review.",
        },
        "payload": valid,
    }
    assert worker.call_tool("worker_validate_output", {"content": result})["valid"]
    worker.call_tool(
        "worker_finalize",
        {"content": result},
    )
    output_name = root.call_tool("task_status", {"name": task_name})["output_artifact_name"]
    output_id = runtime.scheduler_bindings.resolve(
        instance="test", namespace="artifact", name=output_name
    )
    output = runtime.artifacts.get_by_id(output_id)
    assert output.schema_id == "scidiscovery.scientific-intake.v1"
    assert output.kind == "scientific_intake"
