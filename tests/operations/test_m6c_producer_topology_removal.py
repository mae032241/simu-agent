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


@pytest.mark.parametrize("producer_id, port", (
    ("tcad.deck.author.initial.v1", "project"),
    ("tcad.deck.author.revise.v1", "project"),
    ("tcad.deck.author.runtime-failure.v1", "project"),
))
def test_tcad_review_prior_signal_keeps_the_exact_producer_review_edge(producer_id, port):
    catalog = _catalog()
    producer = catalog.operation(producer_id)
    reviewer = catalog.operation("tcad.deck.review.v1")
    subject = next(item for item in reviewer.spec.inputs if item.name == "project")
    assert subject.usage == "prior_signal"
    assert producer.spec.review.reviewer_operation == reviewer.spec.operation_id
    assert producer.spec.review.reviewer_input_port == subject.name
    artifact, envelope = _produced_artifact(catalog, producer_id, port, "tcad_subject")
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    bound = _bound(reviewer, _input(subject.name, subject.usage, artifact))
    routes._validate_producer_output_admission(bound)
    envelope.labels["operation_digest"] = "0" * 64
    routes._validate_producer_output_admission(bound)


_EXISTING_INVENTORY_CONSUMERS = {
    "science.curve.contract.design.v1": ("reference_bundle",),
    "science.curve.contract.review.v1": ("reference_bundle",),
    "science.evidence.audit.intake.v1": ("source_material",),
    "science.evidence.audit.v1": ("source_material",),
    "science.evidence.extract.figure.v2": (
        "paper_source", "figure_request", "figure_manifest", "validation_report",
        "source_panels", "audit_overlays", "curve_tables",
    ),
    "science.figure.evidence.audit.v1": (
        "paper_source", "figure_request", "figure_manifest", "validation_report",
        "source_panels", "audit_overlays", "curve_tables",
    ),
    "science.figure.request.prepare.v1": ("paper_source",),
    "tcad.parameter.evidence.audit.v1": (
        "required_parameter_checklist", "parameter_requirements", "device_parameters",
        "source_catalog", "source_material",
    ),
    "tcad.parameter.evidence.extract.v1": ("source_material",),
}


def test_agent_inventory_exception_has_an_explicit_complete_consumer_inventory(monkeypatch) -> None:
    from scidiscovery.operations import catalog as catalog_module
    from scidiscovery.operations.spec import OPERATION_ABI_VERSION

    assert OPERATION_ABI_VERSION == "17"
    catalog = _catalog()
    actual = {
        operation_id: tuple(port.name for port in catalog.operation(operation_id).spec.inputs
                            if port.usage == "evidence_inventory")
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.executor.kind == "agent"
        and any(port.usage == "evidence_inventory" for port in catalog.operation(operation_id).spec.inputs)
    }
    assert actual == {
        **_EXISTING_INVENTORY_CONSUMERS,
        "science.experiment.design.v1": ("current_progress", "experiment_results", "result_analysis"),
        "science.object.review.v1": ("current_progress", "experiment_results", "result_analysis"),
        "science.result.diagnose.v1": ("experiment_results", "reference_material", "current_progress"),
        "tcad.result.analyze.v1": ("solver_outputs", "reference_material", "current_progress"),
        "science.experiment.revise.v1": ("current_progress",),
        "tcad.deck.author.initial.v1": ("current_progress",),
        "tcad.deck.author.revise.v1": ("current_progress",),
        "tcad.deck.author.runtime-failure.v1": ("current_progress",),
        "tcad.deck.review.v1": ("current_progress",),
    }
    monkeypatch.setattr(catalog_module, "OPERATION_ABI_VERSION", "16")
    prior_abi = _catalog()
    assert all(catalog.operation(operation_id).digest != prior_abi.operation(operation_id).digest
               for operation_id in catalog.operation_ids())


@pytest.mark.parametrize("operation_id", tuple(_EXISTING_INVENTORY_CONSUMERS))
def test_existing_agent_inventory_reads_skip_stale_producer_contracts(operation_id) -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.revise.v1", "experiment_plan", "stale_inventory")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    routes._operation_output_contract = Mock(side_effect=AssertionError("inventory must not inspect producer qualification"))
    compiled = catalog.operation(operation_id)
    for port in compiled.spec.inputs:
        if port.usage == "evidence_inventory":
            routes._validate_producer_output_admission(_bound(compiled, _input(port.name, port.usage, artifact)))
    routes._operation_output_contract.assert_not_called()


@pytest.mark.parametrize("usage", ("claim_evidence", "change_request", "review_signal"))
def test_claim_and_review_inputs_keep_stale_producer_rejection(usage) -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.revise.v1", "experiment_plan", "stale_subject")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    compiled = catalog.operation("science.experiment.revise.v1")
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(_bound(compiled, _input("prior_draft", usage, artifact)))
    assert caught.value.reason_code == "input_producer_contract_changed"


def test_transform_inventory_reads_history_without_qualifying_it() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(catalog, "science.experiment.revise.v1", "experiment_plan", "stale_transform_input")
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    compiled = catalog.operation("tcad.execution-context.project.v1")
    routes._validate_producer_output_admission(_bound(compiled, _input("capability", "evidence_inventory", artifact)))


def test_historical_prior_signal_still_requires_exact_current_review() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(
        catalog, "science.hypothesis.propose.v1", "hypothesis_portfolio", "historical_hypotheses"
    )
    envelope.labels["operation_digest"] = "0" * 64
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    designer = catalog.operation("science.experiment.design.v1")
    bound = _bound(designer, _input("hypothesis_portfolio", "prior_signal", artifact))
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(bound)
    assert caught.value.reason_code == "input_independent_review_missing"

    review, review_envelope = _produced_artifact(
        catalog, "science.hypothesis.criticize.v1", "scientific_review", "critic_review"
    )
    routes.artifacts = SimpleNamespace(catalog=lambda ref: {
        artifact.ref: envelope, review.ref: review_envelope,
    }[ref])
    routes._is_exact_reviewer_output = Mock(return_value=False)
    bound = _bound(designer, *bound.inputs, _input("critic_review", "prior_signal", review))
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(bound)
    assert caught.value.reason_code == "input_independent_review_missing"
    routes._is_exact_reviewer_output.return_value = True
    routes._validate_producer_output_admission(bound)
    assert routes._is_exact_reviewer_output.call_args.kwargs["subject_ref"] == artifact.ref


def test_historical_prior_signal_rejects_incompatible_producer_port() -> None:
    catalog = _catalog()
    artifact, envelope = _produced_artifact(
        catalog, "science.experiment.revise.v1", "experiment_plan", "old_schema"
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
        catalog, "science.experiment.revise.v1", "experiment_plan", "missing_identity"
    )
    del envelope.labels[missing]
    routes = _routes(catalog, {artifact.ref.artifact_id: envelope})
    with pytest.raises(OperationInvocationError) as caught:
        routes._validate_producer_output_admission(_bound(
            catalog.operation("science.object.review.v1"),
            _input("experiment_plan", "prior_signal", artifact),
        ))
    assert caught.value.reason_code == "input_producer_contract_unavailable"
    assert caught.value.port == "experiment_plan"
