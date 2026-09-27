"""Attest exact raw execution outputs for scientific result analysis."""
from __future__ import annotations
from typing import Mapping
from scidiscovery.artifact_agent.schema.common import canonical_json
from .project_packager import ExecutionPackage, TCADRuntimeManifest, attest_runtime_contract


def attest_runtime(inputs: Mapping[str, bytes]) -> dict[str, tuple[bytes, ...]]:
    required = {"execution_package", "runtime_manifest"}
    output_labels = set(inputs) - required
    if not required.issubset(inputs) or any(
        not label.startswith("output__") for label in output_labels
    ):
        raise ValueError(
            "runtime attestation requires execution_package, runtime_manifest, "
            "and optional output__<name> payloads"
        )
    report = attest_runtime_contract(
        ExecutionPackage.model_validate_json(
            inputs["execution_package"], strict=True
        ),
        TCADRuntimeManifest.model_validate_json(
            inputs["runtime_manifest"], strict=True
        ),
        output_payloads={
            label.removeprefix("output__"): inputs[label]
            for label in output_labels
        },
    )
    return {
        "runtime_attestation": (canonical_json(report.model_dump(mode="json")),)
    }
