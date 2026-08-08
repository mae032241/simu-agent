from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.portable_bundle import (
    ActiveBundleError,
    ActiveBundleNeed,
    ActiveBundleSelection,
    export_active_research_bundle,
    import_active_research_bundle,
    verify_active_research_bundle,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_sha256


def _runtime(tmp_path: Path, name: str):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    return open_runtime(
        project_root=project,
        state_root=tmp_path / name,
        task_token_secret=os.urandom(32),
        approval_receipt_secret=os.urandom(32),
    )


def _register(runtime, content: bytes, *, kind: str, parents=(), labels=None):
    return runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id="fixture.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
            parent_refs=parents,
            labels=labels or {},
        ),
        idempotency_key=f"fixture:{kind}:{canonical_sha256(content.decode())}",
    )


def test_active_bundle_exports_provenance_and_rebuilds_fresh_identity(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path, "source-state")
    source_instance = source.scheduler_bindings.create_instance(
        name="fig4_source",
        title="Fig.4 source",
        objective="Continue the bounded Fig.4 provenance diagnosis.",
    )
    evidence = _register(
        source,
        b'{"depth_um":[0.0,0.1],"zn_cm3":[1e19,1e17]}',
        kind="digitized_profile",
        labels={"source_path": "research/fig4/profile.json"},
    )
    diagnosis = _register(
        source,
        b'{"verdict":"provenance_open"}',
        kind="diagnostic_report",
        parents=(evidence.ref,),
        labels={
            "execution_id": "exe_source_only",
            "method": "deterministic_full_curve_score",
        },
    )
    source.scheduler_bindings.bind(
        instance=source_instance.instance_id,
        namespace="artifact",
        name="candidate_diagnosis",
        object_id=diagnosis.artifact_id,
        request_fingerprint="a" * 64,
    )
    source.scheduler_bindings.bind(
        instance=source_instance.instance_id,
        namespace="artifact",
        name="source_evidence",
        object_id=evidence.artifact_id,
        request_fingerprint="d" * 64,
    )

    bundle_path = tmp_path / "fig4-active-bundle"
    result = export_active_research_bundle(
        state_root=source.state_root,
        selection=ActiveBundleSelection(
            bundle_name="fig4_active_state",
            instance_name="fig4_source",
            purpose="Move only the evidence needed to continue the diagnosis.",
            artifact_names=("candidate_diagnosis", "source_evidence"),
            unresolved_inputs=(
                ActiveBundleNeed(
                    name="independent_diagnosis",
                    rationale="The candidate is not yet an accepted scientific claim.",
                ),
            ),
        ),
        output=bundle_path,
    )
    assert result["entries"] == 2
    assert result["bound_artifacts"] == 2

    manifest = verify_active_research_bundle(bundle_path)
    assert len(manifest.entries) == 2
    assert manifest.entries[0].semantic_names == ("source_evidence",)
    assert manifest.entries[1].semantic_names == ("candidate_diagnosis",)
    assert manifest.entries[1].parent_keys == (manifest.entries[0].local_key,)
    assert "execution_id" not in manifest.entries[1].labels
    assert manifest.entries[1].removed_label_keys == ("execution_id",)

    target = _runtime(tmp_path, "target-state")
    target_instance = target.scheduler_bindings.create_instance(
        name="fig4_target",
        title="Fig.4 target",
        objective="Resume the imported bounded Fig.4 diagnosis.",
    )
    imported = import_active_research_bundle(
        runtime=target,
        instance_name="fig4_target",
        bundle_path=bundle_path,
    )
    assert imported["registered_entries"] == 2
    assert imported["bound_artifacts"] == (
        "source_evidence",
        "candidate_diagnosis",
    )

    target_child_id = target.scheduler_bindings.resolve(
        instance=target_instance.instance_id,
        namespace="artifact",
        name="candidate_diagnosis",
    )
    target_child = target.artifacts.get_by_id(target_child_id)
    assert target_child.artifact_id != diagnosis.artifact_id
    assert target.artifacts.read(target_child.ref) == b'{"verdict":"provenance_open"}'
    assert len(target_child.parent_refs) == 1
    assert target_child.parent_refs[0].artifact_id != evidence.artifact_id
    assert (
        target.artifacts.read(target_child.parent_refs[0])
        == b'{"depth_um":[0.0,0.1],"zn_cm3":[1e19,1e17]}'
    )

    replay = import_active_research_bundle(
        runtime=target,
        instance_name="fig4_target",
        bundle_path=bundle_path,
    )
    assert replay == imported
    assert len(target.artifacts.list_artifacts()) == 2


def test_active_bundle_does_not_pull_unselected_control_or_context(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path, "source-state")
    instance = source.scheduler_bindings.create_instance(
        name="source",
        title="Source",
        objective="Separate explicit scientific state from control history.",
    )
    unrelated = _register(
        source,
        b'{"old_control_context":true}',
        kind="agent_task",
    )
    result = _register(
        source,
        b'{"scientific_result":1}',
        kind="diagnostic_report",
        parents=(unrelated.ref,),
    )
    source.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="current_result",
        object_id=result.artifact_id,
        request_fingerprint="c" * 64,
    )

    bundle = tmp_path / "selected-only"
    export_active_research_bundle(
        state_root=source.state_root,
        selection=ActiveBundleSelection(
            bundle_name="selected_only",
            instance_name="source",
            purpose="Move only explicitly selected scientific state.",
            artifact_names=("current_result",),
        ),
        output=bundle,
    )
    manifest = verify_active_research_bundle(bundle)
    assert len(manifest.entries) == 1
    assert manifest.entries[0].parent_keys == ()
    assert manifest.entries[0].omitted_parent_refs[0].sha256 == unrelated.sha256
    payloads = tuple((bundle / "payloads").iterdir())
    assert len(payloads) == 1
    assert payloads[0].read_bytes() == b'{"scientific_result":1}'


def test_active_bundle_verification_rejects_payload_tampering(tmp_path: Path) -> None:
    source = _runtime(tmp_path, "source-state")
    instance = source.scheduler_bindings.create_instance(
        name="source",
        title="Source",
        objective="Create a portable integrity fixture.",
    )
    artifact = _register(source, b'{"value":1}', kind="fixture")
    source.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name="result",
        object_id=artifact.artifact_id,
        request_fingerprint="b" * 64,
    )
    bundle = tmp_path / "bundle"
    export_active_research_bundle(
        state_root=source.state_root,
        selection=ActiveBundleSelection(
            bundle_name="integrity_fixture",
            instance_name="source",
            purpose="Verify offline payload integrity.",
            artifact_names=("result",),
        ),
        output=bundle,
    )

    tampered = tmp_path / "tampered"
    shutil.copytree(bundle, tampered)
    payload = next((tampered / "payloads").iterdir())
    raw = payload.read_bytes()
    payload.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ActiveBundleError, match="hash mismatch"):
        verify_active_research_bundle(tampered)
