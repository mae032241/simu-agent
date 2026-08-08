from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.transforms import ScientificStateTransformAdapter
from tcad_artifact.project_packager import DeckProjectDraft, DeckProjectPatch
from tcad_artifact.transform_adapter import (
    DECK_COMPARE_PROFILE,
    TCADProjectTransformAdapter,
)


def _project() -> dict[str, object]:
    return {
        "schema_version": 1,
        "tool_profile": "sentaurus-sprocess-r2020.09",
        "files": [{"relative_path": "run.cmd", "content": "exit\n"}],
        "entrypoint": "run.cmd",
        "arguments": [],
        "expected_outputs": [],
        "parameter_bindings": [],
        "runtime_assertions": [],
        "resource_limits": {
            "wall_time_seconds": 60,
            "cpu_time_seconds": 60,
            "max_memory_bytes": 1048576,
            "max_output_bytes": 1048576,
            "max_processes": 4,
        },
    }


def test_root_applies_domain_patch_without_exposing_artifact_identity(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "base.json").write_text(
        json.dumps(_project()), encoding="utf-8"
    )
    (project_root / "patch.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "file_operations": [
                    {
                        "operation": "add",
                        "relative_path": "REVIEW.md",
                        "content": "reviewed\n",
                    }
                ],
                "parameter_binding_operations": [],
                "rationale": "Add a non-executable review record.",
            }
        ),
        encoding="utf-8",
    )
    runtime = open_runtime(
        project_root=project_root,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="transform_test", title="Transform test", objective="Apply one patch."
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            transform_adapters=(TCADProjectTransformAdapter(),),
        )
    )
    for name, path in (("base_project", "base.json"), ("project_patch", "patch.json")):
        root.call_tool(
            "artifact_ingest_file",
            {
                "name": name,
                "relative_path": path,
                "media_type": "application/json",
            },
        )

    request = {
        "name": "revised_project",
        "profile": "tcad.deck-project-apply-patch.v1",
        "inputs": [
            {"source_name": "base_project", "artifact_name": "base_project"},
            {"source_name": "project_patch", "artifact_name": "project_patch"},
        ],
    }
    result = root.call_tool("artifact_transform", request)
    assert [item["output_label"] for item in result["outputs"]] == [
        "primary",
        "diff",
    ]
    assert result == root.call_tool("artifact_transform", request)
    rendered = json.dumps(result).lower()
    assert "artifact_id" not in rendered
    assert "sha256" not in rendered

    revised_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="revised_project",
    )
    revised_envelope = runtime.artifacts.get_by_id(revised_id)
    revised = DeckProjectDraft.model_validate_json(
        runtime.artifacts.read(revised_envelope.ref), strict=True
    )
    assert [item.relative_path for item in revised.files] == ["run.cmd", "REVIEW.md"]

    diff_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="revised_project.diff",
    )
    diff_envelope = runtime.artifacts.get_by_id(diff_id)
    difference = json.loads(runtime.artifacts.read(diff_envelope.ref))
    assert difference["file_changes"] == [
        {"operation": "add", "relative_path": "REVIEW.md"}
    ]
    DeckProjectPatch.model_validate_json(
        (project_root / "patch.json").read_bytes(), strict=True
    )


def test_tcad_transform_compares_two_complete_projects_deterministically() -> None:
    base = _project()
    revised = json.loads(json.dumps(base))
    revised["files"][0]["content"] = "# runtime-only revision\nexit\n"
    revised["expected_outputs"] = [
        {
            "name": "profile",
                "relative_path": "profile.plx",
                "media_type": "text/plain",
                "required": True,
                "max_bytes": 1048576,
            }
        ]

    adapter = TCADProjectTransformAdapter()
    outputs = adapter.transform(
        profile=DECK_COMPARE_PROFILE,
        inputs={
            "base_project": canonical_json(base),
            "revised_project": canonical_json(revised),
        },
    )

    assert len(outputs) == 1
    assert outputs[0].kind == "tcad_project_diff"
    assert outputs[0].schema == "tcad.deck-project-diff.v1"
    difference = json.loads(outputs[0].content)
    assert difference["frozen_field_changes"] == ["expected_outputs"]
    assert difference["file_changes"] == [
        {"operation": "replace", "relative_path": "run.cmd"}
    ]
    assert difference["base_project_sha256"] != difference["revised_project_sha256"]
    assert difference["file_deltas"][0]["relative_path"] == "run.cmd"
    assert "+# runtime-only revision" in difference["file_deltas"][0]["unified_diff"]
    assert outputs == adapter.transform(
        profile=DECK_COMPARE_PROFILE,
        inputs={
            "base_project": canonical_json(base),
            "revised_project": canonical_json(revised),
        },
    )


def test_tcad_project_comparison_rejects_ambiguous_inputs() -> None:
    with pytest.raises(
        ValueError,
        match="requires base_project and revised_project inputs",
    ):
        TCADProjectTransformAdapter().transform(
            profile=DECK_COMPARE_PROFILE,
            inputs={"base_project": canonical_json(_project())},
        )


def test_root_splits_scientific_intake_with_one_primary_binding(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    intake = {
        "problem_frame": {
            "title": "Dark-current frame",
            "scientific_question": "Which bounded study resolves the blocker?",
            "objective": "Qualify one full-device dark-current study.",
            "current_contradiction": "Only a cropped baseline is executable.",
            "scope": "One bounded qualification loop.",
            "foundation_item_keys": ["structure"],
            "observables": [
                {
                    "observable_key": "runtime_regions",
                    "description": "Regions present in the runtime structure.",
                    "role": "numerical_diagnostic",
                    "foundation_item_keys": ["structure"],
                    "acceptance_relevance": "A full-device claim requires all layers.",
                }
            ],
            "claim_boundary": {
                "allowed_claim": "The complete runtime structure is qualified.",
                "required_conditions": ["All declared layers are read back."],
            },
            "stop_conditions": ["A required runtime region is absent."],
        },
        "scientific_foundation": {
            "title": "Dark-current foundation",
            "objective": "Qualify one full-device dark-current study.",
            "summary": "The complete structure remains unqualified.",
            "evidence": [
                {
                    "source_key": "checkpoint",
                    "source_type": "frozen_input",
                    "title": "Research checkpoint",
                    "locator": "research/current.yaml",
                }
            ],
            "items": [
                {
                    "item_key": "structure",
                    "item_type": "structure",
                    "epistemic_status": "runtime_observation",
                    "statement": "The executable baseline has only three regions.",
                    "scope": "Historical baseline only.",
                    "evidence_keys": ["checkpoint"],
                }
            ],
        },
    }
    (project_root / "intake.json").write_bytes(canonical_json(intake))
    runtime = open_runtime(
        project_root=project_root,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="intake_split",
        title="Intake split",
        objective="Split one reviewed scientific intake.",
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            transform_adapters=(ScientificStateTransformAdapter(),),
        )
    )
    root.call_tool(
        "artifact_ingest_file",
        {
            "name": "scientific_intake",
            "relative_path": "intake.json",
            "media_type": "application/json",
        },
    )
    request = {
        "name": "dark_problem_frame",
        "profile": "scidiscovery.scientific-intake-split.v1",
        "inputs": [
            {
                "source_name": "scientific_intake",
                "artifact_name": "scientific_intake",
            }
        ],
    }
    result = root.call_tool("artifact_transform", request)
    assert [item["output_label"] for item in result["outputs"]] == [
        "primary",
        "scientific_foundation",
    ]
    assert [item["artifact_name"] for item in result["outputs"]] == [
        "dark_problem_frame",
        "dark_problem_frame.scientific_foundation",
    ]
    assert result == root.call_tool("artifact_transform", request)


def test_root_deterministically_validates_review_manifest_coverage(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    project = {
        **_project(),
        "realization_manifest": [
            {
                "requirement_key": "entrypoint_contract",
                "category": "numerical_protocol",
                "requirement": "Run the declared entrypoint.",
                "evidence_class": "experiment_plan",
                "evidence_source": "fixture plan",
                "evidence_locator": "baseline case",
                "rationale": "The fixture exercises deterministic review coverage.",
                "implementation_status": "implemented",
                "relative_path": "run.cmd",
                "locator": "exit",
                "verification_mode": "static_review",
                "expected_output_name": None,
            }
        ],
    }
    review = {
        "verdict": "pass",
        "summary": "The fixture project is completely covered.",
        "rationale": "The only requirement maps to the declared entrypoint.",
        "physical_fidelity": "pass",
        "implementation_fidelity": "pass",
        "syntax_fidelity": "pass",
        "numerical_protocol_fidelity": "pass",
        "requirement_reviews": [
            {
                "requirement_key": "entrypoint_contract",
                "status": "pass",
                "rationale": "The locator exists in the complete project.",
            }
        ],
        "findings": [],
        "undeclared_defaults": [],
        "unsupported_constructs": [],
        "missing_inputs": [],
        "execution_ready": True,
        "next_actions": [],
    }
    (project_root / "project.json").write_text(json.dumps(project), encoding="utf-8")
    (project_root / "review.json").write_text(json.dumps(review), encoding="utf-8")
    runtime = open_runtime(
        project_root=project_root,
        state_root=tmp_path / "state",
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )
    instance = runtime.scheduler_bindings.create_instance(
        name="review_validation",
        title="Review validation",
        objective="Validate exact manifest coverage.",
    )
    root = RootMCPRouter(
        RootToolFacade(
            runtime.artifacts,
            runtime.intake,
            tasks=runtime.tasks,
            approvals=runtime.approvals,
            executions=runtime.executions,
            bindings=runtime.scheduler_bindings,
            instance=instance.instance_id,
            transform_adapters=(TCADProjectTransformAdapter(),),
        )
    )
    for name in ("project", "review"):
        root.call_tool(
            "artifact_ingest_file",
            {
                "name": name,
                "relative_path": f"{name}.json",
                "media_type": "application/json",
            },
        )

    result = root.call_tool(
        "artifact_transform",
        {
            "name": "review_attestation",
            "profile": "tcad.deck-review-validate.v1",
            "inputs": [
                {"source_name": "project", "artifact_name": "project"},
                {"source_name": "review", "artifact_name": "review"},
            ],
        },
    )
    assert len(result["outputs"]) == 1
    assert result["outputs"][0] == {
        "output_label": "primary",
        "artifact_name": "review_attestation",
        "kind": "tcad_deck_review_attestation",
        "schema": "tcad.deck-review-attestation.v1",
        "media_type": "application/json",
        "size_bytes": result["outputs"][0]["size_bytes"],
    }
    assert result["outputs"][0]["size_bytes"] > 0

    with pytest.raises(Exception, match="not produced from the exact project"):
        root.call_tool(
            "artifact_transform",
            {
                "name": "unbound_reviewed_package",
                "profile": "tcad.reviewed-deck-package.v1",
                "inputs": [
                    {"source_name": "project", "artifact_name": "project"},
                    {"source_name": "review", "artifact_name": "review"},
                ],
            },
        )

    project_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name="project"
    )
    project_ref = runtime.artifacts.get_by_id(project_id).ref
    review_bytes = (project_root / "review.json").read_bytes()
    reviewed = runtime.artifacts.register(
        review_bytes,
        ArtifactRegistration(
            kind="deck_review",
            schema_id="tcad.deck-review-report.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.intake.creator,
            parent_refs=(project_ref,),
        ),
        idempotency_key="fixture-reviewed-project",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="review_from_project",
        object_id=reviewed.artifact_id,
    )
    packaged = root.call_tool(
        "artifact_transform",
        {
            "name": "reviewed_package",
            "profile": "tcad.reviewed-deck-package.v1",
            "inputs": [
                {"source_name": "project", "artifact_name": "project"},
                {"source_name": "review", "artifact_name": "review_from_project"},
            ],
        },
    )
    assert packaged["outputs"][0]["kind"] == "packaged_project"
    assert packaged["outputs"][0]["schema"] == "tcad.reviewed-deck-package.v1"

    package_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name="reviewed_package",
    )
    package_ref = runtime.artifacts.get_by_id(package_id).ref
    runtime_manifest = runtime.artifacts.register(
        canonical_json(
            {
                "started_at": "2026-08-07T00:00:00Z",
                "completed_at": "2026-08-07T00:00:01Z",
                "terminal_state": "succeeded",
                "exit_code": 0,
                "error": "",
                "outputs": [],
            }
        ),
        ArtifactRegistration(
            kind="execution_output",
            schema_id="opaque",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.intake.creator,
            parent_refs=(package_ref,),
        ),
        idempotency_key="fixture-runtime-manifest",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="runtime_manifest",
        object_id=runtime_manifest.artifact_id,
    )
    attestation = root.call_tool(
        "artifact_transform",
        {
            "name": "runtime_attestation",
            "profile": "tcad.runtime-attestation.v1",
            "inputs": [
                {
                    "source_name": "reviewed_package",
                    "artifact_name": "reviewed_package",
                },
                {
                    "source_name": "runtime_manifest",
                    "artifact_name": "runtime_manifest",
                },
            ],
        },
    )
    assert attestation["outputs"][0]["kind"] == "runtime_attestation"
