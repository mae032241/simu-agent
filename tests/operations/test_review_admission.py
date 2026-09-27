"""Catalog diagnostics describe review capacity without installing a stage gate."""
import pytest

from blind_csv_plugin.contracts import validate_observation_context
from blind_csv_plugin.plugin import AUTHOR, PLUGIN, REVIEWER
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.review_admission import review_receiver_diagnostics, review_input_mode
from scidiscovery.operations.spec import CallableComponent, ComponentRef
from tests.operations import test_l3_review_and_human_policy as lifecycle


def _catalog(receiver):
    ports = REVIEWER.inputs
    if receiver:
        review = REVIEWER.inputs[1].model_copy(update={"name": "review_context", "min_items": 0,
            "schema_id": "blind.csv-review.v1", "schema_resource": ComponentRef("review_schema")})
        if receiver == "inventory":
            review = review.model_copy(update={"schema_id": "*", "media_types": ("*/*",),
                "schema_resource": ComponentRef("wildcard_schema", "general_science"), "codec": ComponentRef("opaque_codec", "general_science"), "usage": "evidence_inventory", "exposure": "on_demand"})
        ports = (*ports, review)
    consumer = REVIEWER.model_copy(update={"operation_id": "blind.csv.consume.v1", "inputs": ports})
    return compile_catalog((CORE_PLUGIN, GENERAL, PLUGIN.model_copy(update={"operations": (*PLUGIN.operations, consumer)})))


@pytest.mark.parametrize("receiver", [None, "typed", "inventory"])
def test_review_receiver_diagnostic_uses_current_plugin_contract(receiver):
    catalog = _catalog(receiver)
    rows = [r for r in review_receiver_diagnostics(catalog) if r["consumer_operation"] == "blind.csv.consume.v1"]
    assert not any(r["subject_port"] == "review_context" for r in rows)
    subject = [r for r in rows if r["subject_port"] == "csv_observation"]
    assert len(subject) == 1
    assert subject[0]["producer_operation"] == "blind.csv.observe.v1"
    assert subject[0]["candidate_ports"] == (("review_context",) if receiver else ())
    assert subject[0]["status"] == ("requires_bound_validation" if receiver else "receiver_missing")
    # Missing receiving capacity is diagnostic only; catalog compilation succeeded.
    review = [r for r in review_receiver_diagnostics(catalog) if r["consumer_operation"] == "blind.csv.review.v1"]
    assert any(r["mode"] == "review_subject" for r in review)


@pytest.mark.parametrize("usage,direct,reviewer,expected", [
    ("evidence_inventory", None, None, "background"),
    ("revision_base", "subject", None, "direct_revision"),
    ("prior_signal", None, "consumer", "review_subject"),
    ("prior_signal", None, "other", "witness"),
])
def test_review_modes_are_independent_of_retired_domain_stages(usage, direct, reviewer, expected):
    assert review_input_mode(operation_id="consumer", port_name="subject", usage=usage,
        direct_base_port=direct, reviewer_operation=reviewer, reviewer_input_port="subject") == expected


@pytest.mark.parametrize("ports", [("csv_observation", "csv_observation"), ("absent",)])
def test_compiler_rejects_invalid_independent_review_subject_ports(ports):
    from scidiscovery.operations.catalog import CatalogCompileError
    reviewer = REVIEWER.model_copy(update={"independent_review_ports": ports})
    plugin = PLUGIN.model_copy(update={"operations": (PLUGIN.operations[0], reviewer)})
    with pytest.raises(CatalogCompileError) as rejected:
        compile_catalog((CORE_PLUGIN, GENERAL, plugin))
    assert rejected.value.reason_code == "independent_review_subject_invalid"


def _restricted_observation_context(payload, sources, handoff):
    # This producer can withhold its claim while preserving the exact CSV facts.
    validate_observation_context(payload, sources, {**handoff, "verdict": "pass"})


RESTRICTED_CONTEXT = CallableComponent("validator", _restricted_observation_context)


def _claim_catalog(*, explore=False):
    components = tuple(component.model_copy(update={
        "implementation": "tests.operations.test_review_admission:RESTRICTED_CONTEXT"})
        if component.component_id == "observation_context" else component
        for component in PLUGIN.components)
    consumer = lifecycle._review_gate_catalog().operation("blind.csv.consume.v1").spec
    consumer = consumer.model_copy(update={"inputs": tuple(
        port.model_copy(update={"usage": "claim_evidence"}) if port.name == "csv_observation" else port
        for port in consumer.inputs)})
    author = AUTHOR.model_copy(update={"consequence": "explore"}) if explore else AUTHOR
    plugin = PLUGIN.model_copy(update={"components": components,
        "operations": (author, REVIEWER, consumer)})
    return compile_catalog((CORE_PLUGIN, GENERAL, plugin))


def _bound_artifact(runtime, instance, name):
    return runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace="artifact", name=name))


def _register_copy(runtime, instance, name, source):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    copied = runtime.artifacts.register(runtime.artifacts.read(source.ref), ArtifactRegistration(
        kind=source.kind, schema_id=source.schema_id, payload_schema_version=1,
        media_type=source.media_type, creator=runtime.actor, parent_refs=source.parent_refs,
        labels=source.labels), idempotency_key=name)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact",
        name=name, object_id=copied.artifact_id)
    return copied


@pytest.mark.parametrize("case", ["revise", "blocked", "other_subject", "restricted_source", "copied_labels"])
def test_exact_review_resolves_only_provenance_backed_producer_restriction(tmp_path, case):
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    catalog, runtime, instance, root = lifecycle._system(
        tmp_path, catalog=_claim_catalog(explore=case in {"restricted_source", "copied_labels"}))
    subject = lifecycle._complete_author(catalog, runtime, root,
        instruction="Record bounded facts and withhold the claim.", conflict="reject",
        verdict="revise" if case == "revise" else "blocked")
    original = _bound_artifact(runtime, instance, subject)
    original_bytes = runtime.artifacts.read(original.ref)
    assert lifecycle._consumer_preflight(root, subject, None)["reason_code"] == "input_scientific_claim_forbidden"
    if case == "restricted_source":
        assert original.labels["scientific_claim_admissible"] == "false"
    review_subject = subject
    if case == "other_subject":
        review_subject = lifecycle._complete_author(catalog, runtime, root,
            instruction="Record a distinct observation.", conflict="create_revision", verdict="blocked")
    elif case == "copied_labels":
        _register_copy(runtime, instance, "copied", original)
        subject = "copied"
    review = lifecycle._complete_review(catalog, runtime, root, name="review", subject_name=review_subject)
    result = lifecycle._consumer_preflight(root, subject, review)
    request = {"name": "consume", "operation_id": "blind.csv.consume.v1",
        "instruction": "Consume only a scientifically admissible observation.", "inputs": [
            {"port": "source_table", "artifact_names": ["source_csv"]},
            {"port": "csv_observation", "artifact_names": [subject]},
            {"port": "independent_review", "artifact_names": [review]}]}
    if case in {"revise", "blocked"}:
        assert result["admissible"], result
        assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    else:
        assert result["reason_code"] == "input_scientific_claim_forbidden", result
        with pytest.raises(RootToolError, match="input_scientific_claim_forbidden"):
            root.call_tool("operation_invoke", request)
    assert runtime.artifacts.read(original.ref) == original_bytes
    assert runtime.artifacts.catalog(original.ref).labels == original.labels


def test_compiler_merges_declared_independent_subject_with_review_edge():
    reviewer = REVIEWER.model_copy(update={"independent_review_ports": ("csv_observation",)})
    plugin = PLUGIN.model_copy(update={"operations": (AUTHOR, reviewer)})
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, plugin))
    assert catalog.operation(REVIEWER.operation_id).spec.independent_review_ports == ("csv_observation",)
