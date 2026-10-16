from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.approval_ui.render import render_review
from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.schema.approval import (
    ApprovalRequest,
    CompiledApprovalIdentity,
    LocalIdentityRef,
    ReviewDocument,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolError,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.execution import ExecutionRequest
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.executions import ExecutionServiceError
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    ApprovalProjectorContext,
    ApprovalSubjectSnapshot,
    effect_operation_plan,
)
from scidiscovery.artifact_agent.runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
    parse_plugin_config_assignments,
)
from scidiscovery.operations.spec import (
    ComponentRef,
    ComponentSpec,
    PluginDefinition,
)
from scidiscovery.operations.tooling import operation_worker_tools
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.execution_control import (
    SolverCapability,
    _write_abandoned_terminal,
)
from tcad_artifact.project_packager import (
    DeckFile,
    DeckProjectDraft,
    DeckReviewReport,
    ProjectInputSlot,
    ProjectPreflightAttestation,
    ProjectResourceLimits,
    ResolvedProjectInput,
    ExecutionPackage,
    TCADRuntimeManifest,
    attest_runtime_contract,
)


def _catalog():
    return compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


def _execution_package(resolved_input_count: int = 0) -> bytes:
    capability = SolverCapability(
        profile_id="r4b-runtime",
        solver_kind="sdevice",
        executable="/opt/fake/sdevice",
        environment={},
        release_evidence="R4-B synthetic lifecycle fixture",
        public_release_label="Synthetic SDevice",
    ).public_snapshot()
    source = "Solve {}\n"
    source_tree = hashlib.sha256()
    source_tree.update(b"main.cmd\0")
    source_tree.update(source.encode("utf-8"))
    source_tree.update(b"\0")
    input_slots = tuple(
        ProjectInputSlot(
            semantic_name=f"input_{index:03d}",
            target_relative_path=f"inputs/input-{index:03d}.json",
            media_type="application/json",
        )
        for index in range(1, resolved_input_count + 1)
    )
    resolved_inputs = tuple(
        ResolvedProjectInput(
            semantic_name=slot.semantic_name,
            target_relative_path=slot.target_relative_path,
            artifact_ref=ArtifactRef(
                artifact_id=f"art_execution_input_{index:03d}",
                sha256=hashlib.sha256(f"input-{index}".encode()).hexdigest(),
                kind="execution_input",
                schema_id="fixture.execution-input.v1",
            ),
            media_type=slot.media_type,
            size_bytes=2,
        )
        for index, slot in enumerate(input_slots, start=1)
    )
    project = DeckProjectDraft(
        tool_profile=capability.profile_id,
        solver_kind="sdevice",
        capability_sha256=capability.capability_sha256,
        files=(DeckFile(relative_path="main.cmd", content=source),),
        input_slots=input_slots,
        entrypoint="main.cmd",
        expected_outputs=(),
        preflight_attestation=ProjectPreflightAttestation(
            source_tree_sha256=source_tree.hexdigest(),
            terminal_state="succeeded",
            exit_code=0,
            diagnostic_layer="complete",
            qualified=True,
            summary="The synthetic direct deck passed bounded preflight.",
        ),
        resource_limits=ProjectResourceLimits(max_storage_bytes=2000000000,
            wall_time_seconds=60,
            cpu_time_seconds=60,
            max_memory_bytes=512 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
        ),
    )
    review = DeckReviewReport(
        verdict="pass",
        capability_sha256=capability.capability_sha256,
        summary="The bounded lifecycle fixture is ready.",
        rationale="All declared implementation dimensions pass.",
        physical_fidelity="pass",
        implementation_fidelity="pass",
        syntax_fidelity="pass",
        numerical_protocol_fidelity="pass",
        execution_ready=True,
    )
    return canonical_json(
        ExecutionPackage(
            project=project,
            review=review,
            capability=capability,
            resolved_inputs=resolved_inputs,
        ).model_dump(mode="json")
    )


def test_abandoned_execution_manifest_remains_attestable(tmp_path: Path) -> None:
    run_directory = tmp_path / "abandoned-run"
    run_directory.mkdir()
    _write_abandoned_terminal(
        run_directory,
        terminal_state="failed",
        exit_code=98,
        error="worker_lost",
    )
    raw = (run_directory / "output_manifest.json").read_bytes()
    manifest = TCADRuntimeManifest.model_validate_json(raw, strict=True)
    assert manifest.started_at is None
    attestation = attest_runtime_contract(
        ExecutionPackage.model_validate_json(_execution_package(), strict=True),
        manifest,
    )
    assert attestation.verdict == "fail"
    assert attestation.terminal_state == "failed"

