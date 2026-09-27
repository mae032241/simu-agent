from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_root_operation_routes import (
    RootOperationRoutes,
)
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import (
    operation_artifact_labels,
)
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


def _routes(catalog, envelopes):
    routes = object.__new__(RootOperationRoutes)
    routes._operation_catalog = catalog
    routes.artifacts = SimpleNamespace(
        catalog=lambda ref: envelopes[ref.artifact_id]
    )
    return routes


def _bound(compiled, *items):
    return SimpleNamespace(compiled=compiled, inputs=tuple(items))


def _input(port_name: str, usage: str, artifact: InvocationArtifact):
    return SimpleNamespace(port_name=port_name, usage=usage, artifact=artifact)






def test_review_signal_cannot_enter_an_unrelated_operation_unconsumed() -> None:
    catalog = _catalog()
    signal = InvocationArtifact(
        artifact_name="unbound_review",
        ref=ArtifactRef(
            artifact_id="art_unbound_review",
            sha256="a" * 64,
            kind="scientific_review",
            schema_id="example.review.v1",
        ),
        schema_id="example.review.v1",
        media_type="application/json",
        size_bytes=16,
    )
    routes = object.__new__(RootOperationRoutes)
    routes._operation_catalog = catalog
    routes._operation_output_contract = Mock(return_value=None)

    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(
            _bound(
                catalog.operation("science.experiment.v1"),
                _input("review", "review_signal", signal),
            )
        )

    assert caught.value.reason_code == "input_review_signal_unbound"


def test_producer_contract_requires_compatible_version_and_port() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(
        catalog,
        "science.evidence.extract.v1",
        "scientific_intake",
        "version_probe",
    )
    envelope.labels["operation_version"] = "stale"
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})

    with pytest.raises(OperationInvocationError) as caught:
        routes._operation_output_contract(artifact)
    assert caught.value.reason_code == "input_producer_contract_changed"


def test_same_version_runtime_drift_preserves_claim_port_type_boundary() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.intake.split.v1", "scientific_foundation", "old_claim")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    assert routes._operation_output_contract(artifact) is not None
    for incompatible in (
        replace(artifact, schema_id="incompatible.v0"),
        replace(artifact, media_type="text/plain"),
        replace(artifact, ref=artifact.ref.model_copy(update={"kind": "wrong_kind"})),
    ):
        with pytest.raises(OperationInvocationError, match="input_producer_port_incompatible"):
            routes._operation_output_contract(incompatible)


def test_explore_or_internal_output_is_intrinsically_nonclaiming() -> None:
    from architecture_operation_test_plugin.plugin import (
        ARCHITECTURE_TEST_PLUGIN,
    )

    catalog = compile_catalog((ARCHITECTURE_TEST_PLUGIN,))
    explore = catalog.operation("builtin.test.agent")
    compiled_transform = catalog.operation("builtin.test.transform")
    internal = replace(
        compiled_transform,
        spec=compiled_transform.spec.model_copy(
            update={"catalog_scope": "internal"}
        ),
    )

    assert operation_artifact_labels(SimpleNamespace(compiled=explore))[
        "scientific_claim_admissible"
    ] == "false"
    assert operation_artifact_labels(SimpleNamespace(compiled=internal))[
        "scientific_claim_admissible"
    ] == "false"




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


@pytest.mark.parametrize("operation_id", tuple(_EXISTING_INVENTORY_CONSUMERS))
def test_existing_agent_inventory_reads_skip_stale_producer_contracts(operation_id) -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.v1", "experiment", "stale_inventory")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    routes._operation_output_contract = Mock(side_effect=AssertionError("inventory must not inspect producer qualification"))
    compiled = catalog.operation(operation_id)
    for port in compiled.spec.inputs:
        if port.usage == "evidence_inventory":
            routes._validate_producer_output_admission(_bound(compiled, _input(port.name, port.usage, artifact)))
    routes._operation_output_contract.assert_not_called()


@pytest.mark.parametrize("usage", ("claim_evidence", "change_request", "review_signal"))
def test_claim_and_review_inputs_keep_incompatible_version_rejection(usage) -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.v1", "experiment", "stale_subject")
    envelope.labels["operation_digest"] = "0" * 64
    envelope.labels["operation_version"] = "incompatible"
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    compiled = catalog.operation("science.experiment.v1")
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(_bound(compiled, _input("prior_draft", usage, artifact)))
    assert caught.value.reason_code == "input_producer_contract_changed"


def test_transform_inventory_reads_history_without_qualifying_it() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.v1", "experiment", "stale_transform_input")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    compiled = catalog.operation("science.intake.split.v1")
    routes._validate_producer_output_admission(_bound(compiled, _input("capability", "evidence_inventory", artifact)))




def test_historical_prior_signal_rejects_incompatible_producer_port() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(
        catalog, "science.experiment.v1", "experiment", "old_schema"
    )
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    artifact = replace(artifact, schema_id="incompatible.v0")
    with pytest.raises(OperationInvocationError) as caught:
        routes._operation_output_contract(artifact, allow_historical=True)
    assert caught.value.reason_code == "input_producer_port_incompatible"


@pytest.mark.parametrize("missing", ("operation_version", "operation_digest"))
def test_historical_prior_signal_requires_complete_provenance(missing) -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(
        catalog, "science.experiment.v1", "experiment", "missing_identity"
    )
    del envelope.labels[missing]
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(_bound(
            catalog.operation("science.object.review.v1"),
            _input("experiment", "prior_signal", artifact),
        ))
    assert caught.value.reason_code == "input_producer_contract_unavailable"
    assert caught.value.port == "experiment"
