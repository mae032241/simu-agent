from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.render import render_review
from scidiscovery.artifact_agent.execution_bridge import (
    AdapterCapability,
    ExecutionBridge,
)
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
from scidiscovery.artifact_agent.schema.execution import (
    ExecutionRequest,
    LocalFileDescriptor,
)
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
    ReviewedDeckPackage,
    TCADRuntimeManifest,
    attest_runtime_contract,
)


class _CapabilityAdapter:
    def supports_preparation_profile(self, value: str) -> bool:
        return value == "tcad.reviewed-deck-package.v2"

    def validate_preparation_payload(
        self, raw: bytes, *, preparation_profile: str
    ) -> None:
        if preparation_profile != "tcad.reviewed-deck-package.v2":
            raise ValueError("unexpected synthetic reviewed package")
        ReviewedDeckPackage.model_validate_json(raw, strict=True)

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        content = (
            b'{"capability_sha256":"' + b"0" * 64
            + b'","fixed_arguments":[],"launch_name":"sdevice",'
            b'"private_fixed_argument_count":0,"profile_id":"configured-sdevice",'
            b'"public_arguments":[],"public_release_label":"Synthetic",'
            b'"schema_version":2,"solver_kind":"sdevice"}'
        )
        return (
            AdapterCapability(
                key="configured-sdevice",
                kind="solver_capability",
                schema_id="tcad.solver-capability.v2",
                payload_schema_version=2,
                media_type="application/json",
                content=content,
                public_summary={"profile": "configured-sdevice"},
            ),
        )


class _CollectingTCADAdapter:
    def __init__(self) -> None:
        self.exchange: Path | None = None
        self.submission: tuple[str, str] | None = None

    @staticmethod
    def supports_preparation_profile(value: str) -> bool:
        return value == "tcad.reviewed-deck-package.v2"

    def validate_preparation_payload(
        self, raw: bytes, *, preparation_profile: str
    ) -> None:
        assert preparation_profile == "tcad.reviewed-deck-package.v2"
        ReviewedDeckPackage.model_validate_json(raw, strict=True)

    def prepare(
        self,
        payload: LocalFileDescriptor,
        *,
        preparation_profile: str,
        exchange_directory: Path,
    ) -> LocalFileDescriptor:
        self.validate_preparation_payload(
            Path(payload.local_path).read_bytes(),
            preparation_profile=preparation_profile,
        )
        self.exchange = exchange_directory
        return payload

    def submit(self, submission: LocalFileDescriptor) -> tuple[str, str]:
        assert Path(submission.local_path).is_file()
        self.submission = ("r4b-runtime-run", "accepted")
        return self.submission

    def lookup_submission(
        self, submission: LocalFileDescriptor
    ) -> tuple[str, str] | None:
        assert Path(submission.local_path).is_file()
        return self.submission

    @staticmethod
    def status(external_run_id: str) -> str:
        assert external_run_id == "r4b-runtime-run"
        return "succeeded"

    @staticmethod
    def cancel(external_run_id: str) -> str:
        assert external_run_id == "r4b-runtime-run"
        return "cancelled"

    def collect(self, external_run_id: str) -> tuple[LocalFileDescriptor, ...]:
        assert external_run_id == "r4b-runtime-run"
        assert self.exchange is not None
        raw = canonical_json(
            TCADRuntimeManifest(
                started_at="2026-08-29T00:00:00Z",
                completed_at="2026-08-29T00:00:01Z",
                terminal_state="succeeded",
                exit_code=0,
                error="",
                outputs=(),
            ).model_dump(mode="json")
        )
        path = self.exchange / "runtime-manifest.json"
        path.write_bytes(raw)
        return (
            LocalFileDescriptor(
                name="tcad_manifest",
                local_path=str(path),
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
                media_type="application/json",
            ),
        )


def _catalog():
    return compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))


def _reviewed_package(resolved_input_count: int = 0) -> bytes:
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
        resource_limits=ProjectResourceLimits(
            wall_time_seconds=60,
            cpu_time_seconds=60,
            max_memory_bytes=512 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_processes=2,
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
        ReviewedDeckPackage(
            project=project,
            review=review,
            capability=capability,
            resolved_inputs=resolved_inputs,
        ).model_dump(mode="json")
    )


def test_tcad_execution_summary_keeps_large_resolved_inputs_approvable() -> None:
    operation = _catalog().operation("tcad.study.execute")
    package_raw = _reviewed_package(4096)
    package_ref = ArtifactRef(
        artifact_id="art_reviewed_package_large",
        sha256=hashlib.sha256(package_raw).hexdigest(),
        kind="packaged_project",
        schema_id="tcad.reviewed-deck-package.v2",
    )
    request = ExecutionRequest(
        execution_id="exe_large_summary",
        executor="tcad",
        preparation_profile="tcad.reviewed-deck-package.v2",
        payload_ref=package_ref,
        created_at="2026-08-31T00:00:00Z",
        compiled_identity=CompiledApprovalIdentity(
            operation_id=operation.spec.operation_id,
            operation_version=operation.spec.version,
            operation_digest=operation.digest,
            approval_contract_digest="a" * 64,
        ),
    )
    request_raw = request.canonical_json()
    request_ref = ArtifactRef(
        artifact_id="art_execution_request_large",
        sha256=hashlib.sha256(request_raw).hexdigest(),
        kind="execution_request",
        schema_id="scidiscovery.execution-request",
    )
    context = ApprovalProjectorContext(
        operation_id=operation.spec.operation_id,
        operation_version=operation.spec.version,
        operation_digest=operation.digest,
        subjects=(
            ApprovalSubjectSnapshot(
                subject_index=0,
                port_name="execution_request",
                item_index=0,
                ref=request_ref,
                schema_id=request_ref.schema_id,
                media_type="application/json",
                size_bytes=len(request_raw),
                parent_refs=(),
                labels=(),
                handoff_verdict=None,
                content=request_raw,
            ),
            ApprovalSubjectSnapshot(
                subject_index=1,
                port_name="reviewed_package",
                item_index=0,
                ref=package_ref,
                schema_id=package_ref.schema_id,
                media_type="application/json",
                size_bytes=len(package_raw),
                parent_refs=(),
                labels=(),
                handoff_verdict=None,
                content=package_raw,
            ),
        ),
    )
    projector_key = next(
        key for key in operation.component_ids if key.endswith("execution_projector")
    )
    document = operation.implementations[projector_key](context)
    assert isinstance(document, ReviewDocument)
    pointers = {
        item.json_pointer
        for section in document.sections
        for item in section.items
        if item.json_pointer is not None
    }
    assert "/resolved_inputs" in pointers
    assert not {"/project", "/review", "/capability"}.intersection(pointers)
    assert sum(len(section.items) for section in document.sections) < 512


def _authorize_through_local_ui(runtime, approval_id: str) -> None:
    launch = runtime.approvals.status(approval_id)
    assert launch.review_path is not None
    query = parse_qs(urlparse(launch.review_path).query)
    review = runtime.approvals.review(
        approval_id, access_token=query["token"][0]
    )
    ui = ApprovalUI(runtime.approvals)
    base = ui.start()
    try:
        parsed = urlparse(base)
        connection = http.client.HTTPConnection(
            parsed.hostname, parsed.port, timeout=5
        )
        connection.request(
            "POST",
            f"/review/{approval_id}/decision",
            body=urlencode(
                {
                    "token": query["token"][0],
                    "csrf": review.csrf_token,
                    "nonce": review.decision_nonce,
                    "selected_option": "authorize_execution",
                    "rationale": "",
                    "confirm": "confirm",
                }
            ),
            headers={
                "Origin": base,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 303
        connection.close()
    finally:
        ui.stop()


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
        ReviewedDeckPackage.model_validate_json(_reviewed_package(), strict=True),
        manifest,
    )
    assert attestation.verdict == "fail"
    assert attestation.terminal_state == "failed"

