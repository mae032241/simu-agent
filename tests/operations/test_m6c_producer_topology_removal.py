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


@pytest.mark.parametrize(
    ("producer_operation", "producer_port"),
    (
        ("science.evidence.extract.figure.v2", "scientific_intake"),
        ("tcad.parameter.evidence.expand.v1", "scientific_intake"),
    ),
)
def test_direct_revision_still_rejects_a_different_reviewer_contract(
    producer_operation: str, producer_port: str
) -> None:
    catalog = _catalog()
    base, envelope = _produced_artifact(
        catalog, producer_operation, producer_port, producer_operation.replace(".", "_")
    )
    routes = _routes(catalog, {base.ref.artifact_id: envelope})
    revision = catalog.operation("science.intake.revise.v1")

    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(
            _bound(revision, _input("prior_draft", "revision_base", base))
        )

    assert caught.value.reason_code == "input_revision_review_contract_mismatch"


def test_change_request_must_be_the_exact_base_reviewer_output() -> None:
    catalog = _catalog()
    base, base_envelope = _produced_artifact(
        catalog,
        "science.evidence.extract.v1",
        "scientific_intake",
        "general_intake",
    )
    request, request_envelope = _produced_artifact(
        catalog,
        "tcad.parameter.evidence.audit.v1",
        "evidence_audit",
        "tcad_parameter_audit",
    )
    routes = _routes(
        catalog,
        {
            base.ref.artifact_id: base_envelope,
            request.ref.artifact_id: request_envelope,
        },
    )
    routes._is_exact_reviewer_output = Mock(return_value=False)
    revision = catalog.operation("science.intake.revise.v1")

    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(
            _bound(
                revision,
                _input("prior_draft", "revision_base", base),
                _input("change_request", "change_request", request),
            )
        )

    assert caught.value.reason_code == "input_change_request_mismatch"
    assert routes._is_exact_reviewer_output.call_args.kwargs[
        "reviewer_operation"
    ] == "science.evidence.audit.intake.v1"
    assert routes._is_exact_reviewer_output.call_args.kwargs[
        "accepted_verdicts"
    ] == ("revise", "blocked", "inconclusive")
    assert routes._is_exact_reviewer_output.call_args.kwargs["subject_ref"] == base.ref


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
                catalog.operation("science.experiment.design.v1"),
                _input("review", "review_signal", signal),
            )
        )

    assert caught.value.reason_code == "input_review_signal_unbound"


def test_producer_contract_requires_exact_version_digest_and_port() -> None:
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


def test_output_contract_has_no_downstream_usage_prediction() -> None:
    catalog = _catalog()
    outputs = tuple(
        port
        for operation_id in catalog.operation_ids()
        for port in catalog.operation(operation_id).spec.outputs
    )
    assert outputs
    assert all("allowed_input_usages" not in type(port).model_fields for port in outputs)


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
