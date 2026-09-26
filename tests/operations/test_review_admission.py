"""Catalog diagnostics describe review capacity without installing a stage gate."""
import pytest

from blind_csv_plugin.plugin import PLUGIN, REVIEWER
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.review_admission import review_receiver_diagnostics, review_input_mode
from scidiscovery.operations.spec import ComponentRef


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
