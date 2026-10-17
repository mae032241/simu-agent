from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN


def _catalog():
    return compile_catalog(
        (
            CORE_PLUGIN,
            GENERAL_PLUGIN,
            CURVE_PLUGIN,
            TCAD_PLUGIN,
            FIGURE_PLUGIN,
        )
    )


def _produced_artifact(catalog, operation_id: str, port_name: str, suffix: str):
    operation = catalog.operation(operation_id)
    port = next(item for item in operation.spec.outputs if item.name == port_name)
    reference = ArtifactRef(
        artifact_id=f"art_{suffix}",
        sha256=(suffix.encode().hex() + "0" * 64)[:64],
        kind=port.kind,
        schema_id=port.schema_id,
    )
    artifact = InvocationArtifact(
        artifact_name=suffix,
        ref=reference,
        schema_id=port.schema_id,
        media_type=port.media_types[0],
        size_bytes=16,
    )
    envelope = SimpleNamespace(
        labels={
            "operation_id": operation_id,
            "operation_version": operation.spec.version,
            "operation_digest": operation.digest,
            "operation_output_port": port_name,
        }
    )
    return artifact, envelope


def _bound(compiled, *items):
    return SimpleNamespace(compiled=compiled, inputs=tuple(items))


def _input(port_name: str, usage: str, artifact: InvocationArtifact):
    return SimpleNamespace(port_name=port_name, usage=usage, artifact=artifact)


_EXISTING_INVENTORY_CONSUMERS = {
    "science.evidence.audit.intake.v1": ("source_material",),
    "science.evidence.audit.v1": ("source_material",),
    "science.evidence.extract.figure.v3": ("paper_source", "figure_provenance", "figure_family"),
    "science.figure.evidence.audit.v2": ("paper_source", "figure_provenance", "figure_family"),
    "tcad.parameter.evidence.extract.v1": ("source_material",),
}


def test_agent_inventory_abi_changes_catalog_identity(monkeypatch) -> None:
    from scidiscovery.operations import catalog as catalog_module
    from scidiscovery.operations.spec import OPERATION_ABI_VERSION

    assert OPERATION_ABI_VERSION.isdigit()
    catalog = _catalog()
    monkeypatch.setattr(catalog_module, "OPERATION_ABI_VERSION", str(int(OPERATION_ABI_VERSION) - 1))
    prior_abi = _catalog()
    assert all(catalog.operation(operation_id).digest != prior_abi.operation(operation_id).digest
               for operation_id in catalog.operation_ids())
