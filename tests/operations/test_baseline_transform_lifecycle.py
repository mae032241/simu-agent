from __future__ import annotations


def test_installed_transform_is_idempotent_and_binds_all_outputs(
    installed_probe,
) -> None:
    installed_probe(
        "core",
        r'''
import json
import os
import tempfile
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration

root_directory = Path(tempfile.mkdtemp(prefix="r0-transform-"))
project = root_directory / "project"
project.mkdir()
objective = "Reproduce one bounded target curve."
intake = {
    "problem_frame": {
        "title": "Minimal frame",
        "scientific_question": "Can the target curve be reproduced?",
        "objective": objective,
        "current_contradiction": "The baseline misses the target.",
        "scope": "One frozen curve.",
        "foundation_item_keys": ["target"],
        "observables": [{
            "observable_key": "profile",
            "description": "Concentration versus depth.",
            "role": "target",
            "foundation_item_keys": ["target"],
            "acceptance_relevance": "It is the frozen comparison target.",
        }],
        "claim_boundary": {
            "allowed_claim": "Only the scoped curve may be compared.",
            "required_conditions": ["All declared gates pass."],
        },
        "stop_conditions": ["Stop after the deterministic split."],
    },
    "scientific_foundation": {
        "title": "Minimal foundation",
        "objective": objective,
        "summary": "One target is frozen.",
        "evidence": [{
            "source_key": "paper",
            "source_type": "frozen_input",
            "title": "Paper fixture",
            "locator": "paper.pdf#figure",
        }],
        "items": [{
            "item_key": "target",
            "item_type": "target_data",
            "epistemic_status": "paper_fact",
            "statement": "The target is the supplied curve.",
            "scope": "The frozen fixture only.",
            "evidence_keys": ["paper"],
        }],
    },
}
(project / "intake.json").write_text(
    json.dumps(intake, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
runtime = open_runtime(
    project_root=project,
    state_root=root_directory / "state",
    approval_receipt_secret=os.urandom(32),
)
instance = runtime.scheduler_bindings.create_instance(
    name="r0_transform",
    title="R0 transform lifecycle",
    objective=objective,
)
root = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=runtime.operation_catalog,
    )
)
intake_artifact = runtime.artifacts.register(
    (project / "intake.json").read_bytes(),
    ArtifactRegistration(
        kind="scientific_intake",
        schema_id="scidiscovery.scientific-intake.v1",
        payload_schema_version=1,
        media_type="application/json",
        creator=runtime.actor,
    ),
    idempotency_key="r3:scientific-intake",
)
runtime.scheduler_bindings.bind(
    instance=instance.instance_id,
    namespace="artifact",
    name="scientific_intake",
    object_id=intake_artifact.artifact_id,
)
audit_artifact = runtime.artifacts.register(
    b"{}",
    ArtifactRegistration(
        kind="evidence_audit",
        schema_id="scidiscovery.evidence-audit.v1",
        payload_schema_version=1,
        media_type="application/json",
        creator=runtime.actor,
    ),
    idempotency_key="r3:evidence-audit",
)
runtime.scheduler_bindings.bind(
    instance=instance.instance_id,
    namespace="artifact",
    name="evidence_audit",
    object_id=audit_artifact.artifact_id,
)
request = {
    "name": "problem_frame",
    "operation_id": "science.intake.split.v1",
    "inputs": [
        {"port": "scientific_intake", "artifact_names": ["scientific_intake"]},
        {"port": "evidence_audit", "artifact_names": ["evidence_audit"]},
    ],
}
first = root.call_tool("operation_invoke", request)
second = root.call_tool("operation_invoke", request)
assert first == second
assert [item["output_label"] for item in first["result"]["outputs"]] == [
    "primary", "scientific_foundation"
]
assert [item["artifact_name"] for item in first["result"]["outputs"]] == [
    "problem_frame", "problem_frame.scientific_foundation"
]

input_id = runtime.scheduler_bindings.resolve(
    instance=instance.instance_id, namespace="artifact", name="scientific_intake"
)
input_ref = runtime.artifacts.get_by_id(input_id).ref
for name in ("problem_frame", "problem_frame.scientific_foundation"):
    artifact_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name=name
    )
    envelope = runtime.artifacts.get_by_id(artifact_id)
    assert envelope.parent_refs == (input_ref, audit_artifact.ref)
    assert envelope.labels["operation_id"] == "science.intake.split.v1"
''',
    )
